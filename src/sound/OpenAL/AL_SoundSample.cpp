/*
===========================================================================

Doom 3 BFG Edition GPL Source Code
Copyright (C) 1993-2012 id Software LLC, a ZeniMax Media company.
Copyright (C) 2013 Robert Beckebans
Copyright (C) 1997-2012 Sam Lantinga <slouken@libsdl.org>  (MS ADPCM decoder)
Copyright (c) 2011 Chris Robinson <chris.kcat@gmail.com> (OpenAL helpers)

This file is part of the Doom 3 BFG Edition GPL Source Code ("Doom 3 BFG Edition Source Code").

Doom 3 BFG Edition Source Code is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Doom 3 BFG Edition Source Code is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Doom 3 BFG Edition Source Code.  If not, see <http://www.gnu.org/licenses/>.

In addition, the Doom 3 BFG Edition Source Code is also subject to certain additional terms. You should have received a copy of these additional terms immediately following the terms and conditions of the GNU General Public License which accompanied the Doom 3 BFG Edition Source Code.  If not, please request a copy in writing from id Software at the address below.

If you have questions concerning this license or the applicable additional terms, you may contact in writing id Software LLC, c/o ZeniMax Media Inc., Suite 120, Rockville, Maryland 20850 USA.

===========================================================================
*/

#include "../snd_local.h"
#include "../../framework/ParallelJobSystem.h"
#include <cstdlib>
#include <memory>
#include <stdint.h>

#define STB_VORBIS_HEADER_ONLY
#include "stb_vorbis.c"
#undef STB_VORBIS_HEADER_ONLY

extern idCVar s_useCompression;
extern idCVar s_noSound;
extern idCVar s_releaseSamplePayload;
extern idCVar s_debugHardware;

#define GPU_CONVERT_CPU_TO_CPU_CACHED_READONLY_ADDRESS( x ) x

const uint32 SOUND_MAGIC_IDMSA = 0x6D7A7274;
static const int ROQ_FILE_MAGIC = 0x1084;
static const int ROQ_SOUND_MONO = 0x1020;
static const int ROQ_SOUND_STEREO = 0x1021;
static const int ROQ_AUDIO_SAMPLE_RATE = 22050;
static const int ROQ_AUDIO_MIN_SAMPLE = -32768;
static const int ROQ_AUDIO_MAX_SAMPLE = 32767;

// Some OpenAL implementations expose a small, process-wide buffer pool.  A
// failed allocation must not turn a successfully loaded map into a fatal
// error; keep the decoded sample available for the voice streaming path and
// avoid repeating the same warning for every remaining sample in the map.
static std::atomic<bool> openQ4_openALBufferAllocationWarningIssued( false );

extern idCVar sys_lang;

/*
========================
RoQAudioDelta
========================
*/
static ID_INLINE int RoQAudioDelta( byte sampleCode )
{
	const int magnitude = sampleCode & 0x7F;
	const int delta = magnitude * magnitude;
	return ( sampleCode & 0x80 ) ? -delta : delta;
}

/*
========================
AllocBuffer
========================
*/
static void* AllocBuffer( int size, const char* name )
{
	return Mem_Alloc( size );
}

/*
========================
FreeBuffer
========================
*/
static void FreeBuffer( void* p )
{
	return Mem_Free( p );
}

template<class type>
static bool openQ4_ReadBigExact( idFile* file, type& value )
{
	return file != NULL && file->ReadBig( value ) == sizeof( value );
}

static bool openQ4_ReadExact( idFile* file, void* buffer, const int size )
{
	if( size < 0 || ( size > 0 && buffer == NULL ) )
	{
		return false;
	}
	return size == 0 || ( file != NULL && file->Read( buffer, size ) == size );
}

static bool openQ4_ReadWaveExact( idWaveFile& wave, void* buffer, const int size )
{
	if( size <= 0 || buffer == NULL )
	{
		return false;
	}
	return wave.Read( buffer, size ) == ( size_t )size;
}

/*
========================
openQ4_GetMSADPCMDecodedSize

Validates the MS ADPCM block geometry before any arithmetic is narrowed to
the engine's legacy int-sized allocation and sample-count interfaces.
========================
*/
static bool openQ4_GetMSADPCMDecodedSize( const uint32_t encodedBytes, const uint16_t blockSize,
	const uint16_t samplesPerBlock, const uint16_t channels, const uint16_t numCoefficients,
	size_t& decodedBytes )
{
	decodedBytes = 0;
	if( encodedBytes == 0 || blockSize == 0 || ( channels != 1 && channels != 2 ) ||
		samplesPerBlock < 2 || numCoefficients == 0 || numCoefficients > 7 || encodedBytes % blockSize != 0 )
	{
		return false;
	}

	const uint64_t blockHeaderBytes = static_cast<uint64_t>( channels ) * 7u;
	const uint64_t samplesAfterHeader =
		( static_cast<uint64_t>( samplesPerBlock ) - 2u ) * static_cast<uint64_t>( channels );
	if( ( samplesAfterHeader & 1u ) != 0 )
	{
		return false;
	}

	const uint64_t encodedSampleBytes = samplesAfterHeader / 2u;
	if( blockHeaderBytes + encodedSampleBytes != static_cast<uint64_t>( blockSize ) )
	{
		return false;
	}

	const uint64_t blockCount = static_cast<uint64_t>( encodedBytes ) / blockSize;
	const uint64_t decodedByteCount = blockCount * static_cast<uint64_t>( samplesPerBlock ) *
		static_cast<uint64_t>( channels ) * sizeof( int16_t );
	if( decodedByteCount == 0 || decodedByteCount > static_cast<uint64_t>( idMath::INT_MAX ) )
	{
		return false;
	}

	// idMath::INT_MAX is no larger than SIZE_MAX on every supported target.
	decodedBytes = static_cast<size_t>( decodedByteCount );
	return true;
}

/*
========================
SoundSample_AppendUniqueSampleVariant
========================
*/
static void SoundSample_AppendUniqueSampleVariant( idList< idStr >& variants, const idStr& name )
{
	for( int i = 0; i < variants.Num(); i++ )
	{
		// Icmp so the probe list does not gain a duplicate entry on
		// case-insensitive hosts while still being correct on Linux
		if( variants[ i ].Icmp( name ) == 0 )
		{
			return;
		}
	}
	variants.Append( name );
}

/*
========================
SoundSample_AppendLocalizedVOVariants

Sound shaders reference the unlocalized 'sound/vo/...' path, but the retail
data only ships voice-over under a per-language tree. Add both spellings retail
used for a given language.
========================
*/
static void SoundSample_AppendLocalizedVOVariants( idList< idStr >& variants, const idStr& baseName, const char* language )
{
	if( language == NULL || language[ 0 ] == '\0' )
	{
		return;
	}

	idStr localized = baseName;
	if( localized.Replace( "/vo/", va( "/vo_%s/", language ) ) )
	{
		SoundSample_AppendUniqueSampleVariant( variants, localized );
	}

	localized = baseName;
	if( localized.Replace( "/vo/", va( "/vo/%s/", language ) ) )
	{
		SoundSample_AppendUniqueSampleVariant( variants, localized );
	}
}

/*
========================
SoundSample_AppendMissingQ4StockFallback

The retail ambient_water_splash_big shader names a sample that was omitted
from the shipped PK4s. Probe the authored path first so mods can supply it,
then fall back to the shipped splash from the same sound family.
========================
*/
static void SoundSample_AppendMissingQ4StockFallback( idList< idStr >& variants, const idStr& baseName )
{
	idStr canonicalName = baseName;
	canonicalName.BackSlashesToSlashes();
	canonicalName.StripFileExtension();
	if( canonicalName.Icmp( "sound/ambience/water/splash_big" ) == 0 )
	{
		SoundSample_AppendUniqueSampleVariant( variants, "sound/ambience/water/splash_small02" );
	}
}

static bool openQ4_CanUploadSampleToOpenAL()
{
	ALCcontext* const expectedContext = soundSystemLocal.hardware.GetOpenALContext();
	if( expectedContext == NULL )
	{
		// Sound samples can be parsed before the OpenAL device is initialized.
		return false;
	}

	ALCcontext* const currentContext = alcGetCurrentContext();
	if( currentContext == expectedContext )
	{
		return true;
	}

	if( currentContext == NULL )
	{
		return alcMakeContextCurrent( expectedContext ) != 0;
	}

	return false;
}

/*
========================
idSoundSample_OpenAL::idSoundSample_OpenAL
========================
*/
idSoundSample_OpenAL::idSoundSample_OpenAL()
{
	pendingDecode = NULL;
	timestamp = FILE_NOT_FOUND_TIMESTAMP;
	loaded = false;
	neverPurge = false;
	levelLoadReferenced = false;

	memset( &format, 0, sizeof( format ) );

	totalBufferSize = 0;

	playBegin = 0;
	playLength = 0;

	lastPlayedTime = 0;

	payloadReleased = false;
	// deliberately not cleared by FreeData: LoadResource frees before it
	// reloads, and the whole point of the flag is to survive that
	keepPayload = false;
	openalBuffer = 0;
	openalBufferUploadFailed = false;
}

/*
========================
idSoundSample_OpenAL::~idSoundSample_OpenAL
========================
*/
idSoundSample_OpenAL::~idSoundSample_OpenAL()
{
	FreeData();
}

/*
========================
idSoundSample_OpenAL::WriteGeneratedSample
========================
*/
void idSoundSample_OpenAL::WriteGeneratedSample( idFile* fileOut )
{
	fileOut->WriteBig( SOUND_MAGIC_IDMSA );
	fileOut->WriteBig( timestamp );
	fileOut->WriteBig( loaded );
	fileOut->WriteBig( playBegin );
	fileOut->WriteBig( playLength );
	idWaveFile::WriteWaveFormatDirect( format, fileOut );
	fileOut->WriteBig( ( int )amplitude.Num() );
	fileOut->Write( amplitude.Ptr(), amplitude.Num() );
	fileOut->WriteBig( totalBufferSize );
	fileOut->WriteBig( ( int )buffers.Num() );
	for( int i = 0; i < buffers.Num(); i++ )
	{
		fileOut->WriteBig( buffers[ i ].numSamples );
		fileOut->WriteBig( buffers[ i ].bufferSize );
		fileOut->Write( buffers[ i ].buffer, buffers[ i ].bufferSize );
	};
}
/*
========================
idSoundSample_OpenAL::WriteAllSamples
========================
*/
void idSoundSample_OpenAL::WriteAllSamples( const idStr& sampleName )
{
	idSoundSample_OpenAL* samplePC = new idSoundSample_OpenAL();
	{
		idStr inName = sampleName;
		inName.Append( ".msadpcm" );
		idStr inName2 = sampleName;
		inName2.Append( ".wav" );

		idStr outName = "generated/";
		outName.Append( sampleName );
		outName.Append( ".idwav" );

		if( samplePC->LoadWav( inName ) || samplePC->LoadWav( inName2 ) )
		{
			// the generated/ tree is regenerable cache, and fs_basepath is
			// commonly the read-only game install (SAF-backed storage on
			// Android, Program Files on Windows); fs_cachepath is always
			// writable and falls back to fs_savepath when the host leaves it unset
			idFile* fileOut = fileSystem->OpenFileWrite( outName, "fs_cachepath" );
			samplePC->WriteGeneratedSample( fileOut );
			delete fileOut;
		}
	}
	delete samplePC;
}

/*
========================
idSoundSample_OpenAL::LoadGeneratedSound
========================
*/
bool idSoundSample_OpenAL::LoadGeneratedSample( const idStr& filename )
{
#if 1
	idFileLocal fileIn( fileSystem->OpenFileRead( filename ) );
	if( fileIn != NULL )
	{
		FreeData();

		const int fileLength = fileIn->Length();
		uint32 magic;
		if( !openQ4_ReadBigExact( fileIn, magic ) || magic != SOUND_MAGIC_IDMSA )
		{
			return false;
		}
		if( !openQ4_ReadBigExact( fileIn, timestamp ) ||
			!openQ4_ReadBigExact( fileIn, loaded ) ||
			!openQ4_ReadBigExact( fileIn, playBegin ) ||
			!openQ4_ReadBigExact( fileIn, playLength ) ||
			playBegin < 0 ||
			playLength < 0 )
		{
			return false;
		}
		if( !idWaveFile::ReadWaveFormatDirect( format, fileIn ) )
		{
			return false;
		}
		int num;
		if( !openQ4_ReadBigExact( fileIn, num ) || num < 0 || num > fileLength )
		{
			return false;
		}
		amplitude.Clear();
		amplitude.SetNum( num );
		if( !openQ4_ReadExact( fileIn, amplitude.Ptr(), amplitude.Num() ) )
		{
			amplitude.Clear();
			return false;
		}
		if( !openQ4_ReadBigExact( fileIn, totalBufferSize ) || totalBufferSize <= 0 )
		{
			return false;
		}
		if( !openQ4_ReadBigExact( fileIn, num ) || num <= 0 || num > totalBufferSize )
		{
			return false;
		}
		buffers.SetNum( num );
		int remainingBufferBytes = totalBufferSize;
		for( int i = 0; i < num; i++ )
		{
			buffers[ i ].buffer = NULL;
			if( !openQ4_ReadBigExact( fileIn, buffers[ i ].numSamples ) ||
				!openQ4_ReadBigExact( fileIn, buffers[ i ].bufferSize ) ||
				buffers[ i ].numSamples < 0 ||
				buffers[ i ].bufferSize <= 0 ||
				buffers[ i ].bufferSize > remainingBufferBytes )
			{
				for( int j = 0; j < i; j++ )
				{
					FreeBuffer( buffers[ j ].buffer );
				}
				buffers.Clear();
				return false;
			}
			buffers[ i ].buffer = AllocBuffer( buffers[ i ].bufferSize, GetName() );
			if( buffers[ i ].buffer == NULL || !openQ4_ReadExact( fileIn, buffers[ i ].buffer, buffers[ i ].bufferSize ) )
			{
				for( int j = 0; j <= i; j++ )
				{
					FreeBuffer( buffers[ j ].buffer );
				}
				buffers.Clear();
				return false;
			}
			buffers[ i ].buffer = GPU_CONVERT_CPU_TO_CPU_CACHED_READONLY_ADDRESS( buffers[ i ].buffer );
			remainingBufferBytes -= buffers[ i ].bufferSize;
		}
		if( remainingBufferBytes != 0 )
		{
			for( int i = 0; i < buffers.Num(); i++ )
			{
				FreeBuffer( buffers[ i ].buffer );
			}
			buffers.Clear();
			return false;
		}
		return true;
	}
#endif

	return false;
}

/*
========================
SoundSample_BuildVariants

The files LoadResource probes for a sample, in order.
========================
*/
static void SoundSample_BuildVariants( const char* name, idList< idStr >& sampleVariants )
{
	idStr baseSampleName = name;
	if( baseSampleName.Find( "/vo/" ) >= 0 )
	{
		SoundSample_AppendLocalizedVOVariants( sampleVariants, baseSampleName, sys_lang.GetString() );

		// Retail Quake 4 resolves the voice-over language separately from the
		// text language (idSoundSample::Load -> SoundSample_SelectVOLanguage)
		// and falls back to English for any language that ships localized
		// subtitles but no localized voice track. Without this a text-only
		// language pack silences every line of dialogue while lip-sync, which
		// is driven from the decl rather than the sample, keeps animating.
		SoundSample_AppendLocalizedVOVariants( sampleVariants, baseSampleName, "english" );
	}
	SoundSample_AppendUniqueSampleVariant( sampleVariants, baseSampleName );
	SoundSample_AppendMissingQ4StockFallback( sampleVariants, baseSampleName );
}

/*
========================
idSoundSample_OpenAL::LoadResource
========================
*/
void idSoundSample_OpenAL::LoadResource()
{
	FreeData();

	if( idStr::Icmpn( GetName(), "_default", 8 ) == 0 )
	{
		MakeDefault();
		return;
	}

	if( s_noSound.GetBool() )
	{
		MakeDefault();
		return;
	}

	loaded = false;

	idList< idStr > sampleVariants;
	SoundSample_BuildVariants( GetName(), sampleVariants );

	for( int i = 0; i < sampleVariants.Num(); i++ )
	{
		idStr sampleName = sampleVariants[ i ];
		idStr generatedName = "generated/";
		generatedName.Append( sampleName );

		{
			idStr ext;
			sampleName.ExtractFileExtension( ext );
			ext.ToLower();
			const bool preferRoQ = ( ext.Icmp( "roq" ) == 0 );

			idStr wavName = sampleName;
			wavName.SetFileExtension( ".wav" );

			idStr oggName = sampleName;
			oggName.SetFileExtension( ".ogg" );

			idStr roqName = sampleName;
			roqName.SetFileExtension( ".roq" );

			generatedName.SetFileExtension( ".idwav" );

			if( preferRoQ )
			{
				loaded = LoadRoQ( roqName );
			}
			else
			{
				loaded = false;
			}

			if( !loaded )
			{
				loaded = LoadOgg( oggName );
			}

			if( !loaded )
			{
				loaded = LoadGeneratedSample( generatedName ) || LoadWav( wavName );
			}

			if( !loaded && !preferRoQ )
			{
				loaded = LoadRoQ( roqName );
			}
		}

		if( loaded )
		{
			//if( cvarSystem->GetCVarBool( "fs_buildresources" ) )
			//{
			//	fileSystem->AddSamplePreload( GetName() );
			//	WriteAllSamples( GetName() );
			//
			//	if( sampleName.Find( "/vo/" ) >= 0 )
			//	{
			//		for( int i = 0; i < Sys_NumLangs(); i++ )
			//		{
			//			const char* lang = Sys_Lang( i );
			//			if( idStr::Icmp( lang, ID_LANG_ENGLISH ) == 0 )
			//			{
			//				continue;
			//			}
			//			idStrStatic< MAX_OSPATH > locName = GetName();
			//			locName.Replace( "/vo/", va( "/vo/%s/", Sys_Lang( i ) ) );
			//			WriteAllSamples( locName );
			//		}
			//	}
			//}

			// upload PCM data to OpenAL
			CreateOpenALBuffer();

			return;
		}
	}

	if( !loaded )
	{
		// Retail warns unconditionally here (idSoundSample::Load). Without it a
		// sample that resolves to nothing is completely invisible in the log,
		// which is how "no character audio at all" reports end up undiagnosable.
		// Name every path probed: for voice-over the probe list is rewritten
		// from the shader's unlocalized 'sound/vo/...' name, so the failing
		// filename is not the one the material author wrote.
		idStr probed;
		for( int i = 0; i < sampleVariants.Num(); i++ )
		{
			if( i > 0 )
			{
				probed += ", ";
			}
			probed += sampleVariants[ i ];
		}
		idLib::Warning( "Couldn't load sound '%s' using default (probed: %s)", GetName(), probed.c_str() );

		// make it default if everything else fails
		MakeDefault();
	}
	return;
}

/*
========================
SoundSample_BuildAmplitudeEnvelope

The peak of every 1/60 s of 16-bit PCM as 0-255, the rate GetAmplitude reads. Camera
shakes, controller rumble and sound-driven lights follow it. Retail measured the decoded
samples for this; the .amp files the BFG path expected never shipped with Quake 4.
========================
*/
static void SoundSample_BuildAmplitudeEnvelope( const int16* pcm, const uint32 bytes, const int channels, const int rate, idList<byte>& out )
{
	out.Clear();
	if( pcm == NULL || channels <= 0 || rate <= 0 )
	{
		return;
	}
	const int64 frames = bytes / ( sizeof( int16 ) * channels );
	const int64 entries = ( frames * 60 + rate - 1 ) / rate;
	if( frames <= 0 || entries <= 0 || entries > 60 * 60 * 60 )
	{
		return;
	}
	out.SetNum( static_cast<int>( entries ) );
	for( int64 entry = 0; entry < entries; entry++ )
	{
		const int64 first = ( entry * rate / 60 ) * channels;
		const int64 last = Min( frames, ( entry + 1 ) * rate / 60 ) * channels;
		int peak = 0;
		for( int64 i = first; i < last; i++ )
		{
			const int value = pcm[i] < 0 ? -pcm[i] : pcm[i];
			peak = ( value > peak ) ? value : peak;
		}
		out[static_cast<int>( entry )] = static_cast<byte>( Min( 255, ( peak * 255 + 16383 ) / 32767 ) );
	}
}

void idSoundSample_OpenAL::CreateOpenALBuffer()
{
	if( pendingDecode != NULL )
	{
		// uploads once the PCM is in
		FinishDecode();
		return;
	}
	if( openalBuffer != 0 || openalBufferUploadFailed )
	{
		return;
	}

	// FreeData() empties the buffer list; there is nothing to upload until the
	// sample is loaded again
	if( buffers.Num() <= 0 || buffers[0].buffer == NULL )
	{
		return;
	}

	if( !openQ4_CanUploadSampleToOpenAL() )
	{
		return;
	}

	// build OpenAL buffer
	CheckALErrors();
	alGenBuffers( 1, &openalBuffer );

	const ALenum allocationError = CheckALErrors();
	if( allocationError != AL_NO_ERROR || openalBuffer == 0 || !alIsBuffer( openalBuffer ) )
	{
		if( openalBuffer != 0 && alIsBuffer( openalBuffer ) )
		{
			alDeleteBuffers( 1, &openalBuffer );
			CheckALErrors();
		}
		openalBuffer = 0;
		openalBufferUploadFailed = true;
		if( !openQ4_openALBufferAllocationWarningIssued.exchange( true, std::memory_order_relaxed ) )
		{
			common->Warning(
				"OpenAL could not allocate another sample buffer (error 0x%x, sample '%s'); "
				"continuing with streaming fallback where resources permit. Further allocation failures are suppressed.",
				allocationError,
				GetName() );
		}
		return;
	}

	if( alIsBuffer( openalBuffer ) )
	{
		CheckALErrors();

		void* buffer = NULL;
		uint32 bufferSize = 0;

		if( format.basic.formatTag == idWaveFile::FORMAT_ADPCM )
		{
			// RB: decode idWaveFile::FORMAT_ADPCM to idWaveFile::FORMAT_PCM

			buffer = buffers[0].buffer;
			bufferSize = buffers[0].bufferSize;

			if( MS_ADPCM_decode( ( uint8** ) &buffer, &bufferSize ) < 0 )
			{
				idLib::Warning( "idSoundSample_OpenAL::CreateOpenALBuffer: could not decode ADPCM '%s' to 16 bit format", GetName() );
				alDeleteBuffers( 1, &openalBuffer );
				CheckALErrors();
				openalBuffer = 0;
				openalBufferUploadFailed = true;
				return;
			}

			buffers[0].buffer = buffer;
			buffers[0].bufferSize = bufferSize;

			totalBufferSize = bufferSize;
		}
		else if( format.basic.formatTag == idWaveFile::FORMAT_XMA2 || format.basic.formatTag == idWaveFile::FORMAT_EXTENSIBLE )
		{
			// LoadWav refuses XMA2 and turns extensible PCM into plain PCM, so this is only a guard
			idLib::Warning( "idSoundSample_OpenAL::CreateOpenALBuffer: '%s' is not 16-bit PCM", GetName() );
			alDeleteBuffers( 1, &openalBuffer );
			CheckALErrors();
			openalBuffer = 0;
			openalBufferUploadFailed = true;
			return;
		}
		else
		{
			// TODO concatenate buffers

			assert( buffers.Num() == 1 );

			buffer = buffers[0].buffer;
			bufferSize = buffers[0].bufferSize;
		}

#if 0 //#if defined(AL_SOFT_buffer_samples)
		if( alIsExtensionPresent( "AL_SOFT_buffer_samples" ) )
		{
			ALenum type = AL_SHORT_SOFT;

			if( format.basic.bitsPerSample != 16 )
			{
				//common->Error( "idSoundSample_OpenAL::LoadResource: '%s' not a 16 bit format", GetName() );
			}

			ALenum channels = NumChannels() == 1 ? AL_MONO_SOFT : AL_STEREO_SOFT;
			ALenum alFormat = GetOpenALSoftFormat( channels, type );

			alBufferSamplesSOFT( openalBuffer, format.basic.samplesPerSec, alFormat, BytesToFrames( bufferSize, channels, type ), channels, type, buffer );
		}
		else
#endif
		{
			if( amplitude.Num() == 0 && !IsDefault() )
			{
				SoundSample_BuildAmplitudeEnvelope( static_cast<const int16*>( buffer ), bufferSize, NumChannels(), format.basic.samplesPerSec, amplitude );
			}
			alBufferData( openalBuffer, GetOpenALBufferFormat(), buffer, bufferSize, format.basic.samplesPerSec );
		}

		const ALenum uploadError = CheckALErrors();
		if( uploadError != AL_NO_ERROR )
		{
			const ALuint failedBuffer = openalBuffer;
			openalBuffer = 0;
			if( alIsBuffer( failedBuffer ) )
			{
				alDeleteBuffers( 1, &failedBuffer );
				CheckALErrors();
			}
			openalBufferUploadFailed = true;
			common->Warning(
				"OpenAL could not upload sample '%s' (error 0x%x); continuing with streaming fallback where resources permit.",
				GetName(),
				uploadError );
		}

		// OpenAL owns a copy of these bytes now; ours is redundant
		ReleaseCpuPayload();
	}
}

/*
========================
idSoundSample_OpenAL::ReleaseCpuPayload

alBufferData copied every byte into OpenAL's own storage, so what is left in
buffers[] is a second resident copy of the same PCM. Free the payload but keep
the sampleBuffer_t entries: RestartAt and GetPlayableBufferRange navigate a
sample through numSamples and bufferSize, and only the streaming submit path
dereferences the bytes.

Not done for a sample split across several buffers. CreateOpenALBuffer only
uploads the single-buffer case -- it asserts as much -- so a multi-buffer sample
has no complete OpenAL copy to fall back on.
========================
*/
void idSoundSample_OpenAL::ReleaseCpuPayload()
{
	if( payloadReleased || keepPayload || !s_releaseSamplePayload.GetBool() )
	{
		return;
	}
	if( openalBuffer == 0 || buffers.Num() != 1 )
	{
		return;
	}

	FreeBuffer( buffers[0].buffer );
	buffers[0].buffer = NULL;
	payloadReleased = true;
}

/*
========================
idSoundSample_OpenAL::EnsureCpuPayload

Restore through a temporary sample. Other voices may still be using our OpenAL
buffer, so reloading this object would delete an attached buffer and invalidate
their playback state. Only transfer matching CPU bytes; retain our metadata and
OpenAL handle.
========================
*/
bool idSoundSample_OpenAL::EnsureCpuPayload()
{
	FinishDecode();
	if( !payloadReleased )
	{
		return buffers.Num() > 0 && buffers[0].buffer != NULL;
	}

	// Set before the reload, not after: LoadResource ends by uploading to
	// OpenAL, which would otherwise release the payload we are restoring.
	keepPayload = true;

	// This costs a synchronous decode in the middle of starting a sound, so it
	// is worth seeing when it happens. It should be rare and it should never
	// repeat for the same sample -- keepPayload is sticky.
	if( s_debugHardware.GetBool() )
	{
		idLib::Printf( "%dms: reloading released payload for %s\n", Sys_Milliseconds(), GetName() );
	}
	idSoundSample_OpenAL restored;
	restored.SetName( GetName() );
	restored.keepPayload = true;
	restored.LoadResource();
	if( !restored.loaded || buffers.Num() != 1 || restored.buffers.Num() != 1 ||
		restored.buffers[0].buffer == NULL ||
		memcmp( &format, &restored.format, sizeof( format ) ) != 0 ||
		playBegin != restored.playBegin || playLength != restored.playLength ||
		buffers[0].numSamples != restored.buffers[0].numSamples ||
		buffers[0].bufferSize != restored.buffers[0].bufferSize )
	{
		// A missing or replaced source must not change already playing voices.
		restored.FreeData();
		return false;
	}
	buffers[0].buffer = restored.buffers[0].buffer;
	restored.buffers[0].buffer = NULL;
	payloadReleased = false;
	restored.FreeData();
	return true;
}

/*
========================
idSoundSample_OpenAL::LoadWav
========================
*/
// A failed attempt frees what it read and returns false; LoadResource tries the next
// loader and language variant and only falls back to the default sound when all fail.
// Making the default here uploaded the beep, and a later variant that loaded found the
// OpenAL buffer taken and played the beep in its place.
bool idSoundSample_OpenAL::LoadWav( const idStr& filename )
{

	// load the wave
	idWaveFile wave;
	if( !wave.Open( filename ) )
	{
		return false;
	}

	idStr sampleName = filename;
	sampleName.SetFileExtension( "amp" );
	LoadAmplitude( sampleName );

	const char* formatError = wave.ReadWaveFormat( format );
	if( formatError != NULL )
	{
		idLib::Warning( "LoadWav( %s ) : %s", filename.c_str(), formatError );
		FreeData();
		return false;
	}
	timestamp = wave.Timestamp();

	const uint32 dataChunkSize = wave.SeekToChunk( 'data' );
	if( dataChunkSize == 0 || dataChunkSize > ( uint32 )idMath::INT_MAX || format.basic.blockSize == 0 )
	{
		idLib::Warning( "LoadWav( %s ) : invalid data chunk", filename.c_str() );
		FreeData();
		return false;
	}
	totalBufferSize = ( int )dataChunkSize;

	if( format.basic.formatTag == idWaveFile::FORMAT_PCM || format.basic.formatTag == idWaveFile::FORMAT_EXTENSIBLE )
	{

		if( format.basic.bitsPerSample != 16 )
		{
			idLib::Warning( "LoadWav( %s ) : %s", filename.c_str(), "Not a 16 bit PCM wav file" );
			FreeData();
			return false;
		}
		// the OpenAL upload is mono or stereo 16-bit; anything else played as noise
		if( format.basic.numChannels < 1 || format.basic.numChannels > 2 || format.basic.blockSize != format.basic.numChannels * 2 )
		{
			idLib::Warning( "LoadWav( %s ) : %d channels with %d byte frames; only mono and stereo 16-bit PCM play", filename.c_str(), format.basic.numChannels, format.basic.blockSize );
			FreeData();
			return false;
		}
		if( totalBufferSize % format.basic.blockSize != 0 )
		{
			idLib::Warning( "LoadWav( %s ) : %s", filename.c_str(), "PCM data is not block aligned" );
			FreeData();
			return false;
		}

		playBegin = 0;
		playLength = ( totalBufferSize ) / format.basic.blockSize;

		buffers.SetNum( 1 );
		buffers[0].bufferSize = totalBufferSize;
		buffers[0].numSamples = playLength;
		buffers[0].buffer = AllocBuffer( totalBufferSize, GetName() );

		if( buffers[0].buffer == NULL || !openQ4_ReadWaveExact( wave, buffers[0].buffer, totalBufferSize ) )
		{
			idLib::Warning( "LoadWav( %s ) : could not read PCM data", filename.c_str() );
			FreeData();
			return false;
		}

		if( format.basic.bitsPerSample == 16 )
		{
			idSwap::LittleArray( ( short* )buffers[0].buffer, totalBufferSize / sizeof( short ) );
		}

		buffers[0].buffer = GPU_CONVERT_CPU_TO_CPU_CACHED_READONLY_ADDRESS( buffers[0].buffer );

	}
	else if( format.basic.formatTag == idWaveFile::FORMAT_ADPCM )
	{
		size_t decodedBytes = 0;
		if( !openQ4_GetMSADPCMDecodedSize( dataChunkSize, format.basic.blockSize,
			format.extra.adpcm.samplesPerBlock, format.basic.numChannels,
			format.extra.adpcm.numCoef, decodedBytes ) )
		{
			idLib::Warning( "LoadWav( %s ) : invalid ADPCM block layout", filename.c_str() );
			FreeData();
			return false;
		}

		playBegin = 0;
		playLength = static_cast<int>( decodedBytes /
			( static_cast<size_t>( format.basic.numChannels ) * sizeof( int16_t ) ) );

		buffers.SetNum( 1 );
		buffers[0].bufferSize = totalBufferSize;
		buffers[0].numSamples = playLength;
		buffers[0].buffer  = AllocBuffer( totalBufferSize, GetName() );

		if( buffers[0].buffer == NULL || !openQ4_ReadWaveExact( wave, buffers[0].buffer, totalBufferSize ) )
		{
			idLib::Warning( "LoadWav( %s ) : could not read ADPCM data", filename.c_str() );
			FreeData();
			return false;
		}
		// The decoder refuses a block whose coefficient selector is out of range, and that
		// refusal at upload ended the session; refuse the file here instead.
		const uint8* adpcm = static_cast<const uint8*>( buffers[0].buffer );
		for( uint32 blockOffset = 0; blockOffset < dataChunkSize; blockOffset += format.basic.blockSize )
		{
			for( int channel = 0; channel < format.basic.numChannels; channel++ )
			{
				if( adpcm[ blockOffset + channel ] >= format.extra.adpcm.numCoef || adpcm[ blockOffset + channel ] >= 7 )
				{
					idLib::Warning( "LoadWav( %s ) : ADPCM block at byte %u selects coefficient %d of %d", filename.c_str(), blockOffset, adpcm[ blockOffset + channel ], format.extra.adpcm.numCoef );
					FreeData();
					return false;
				}
			}
		}

		buffers[0].buffer = GPU_CONVERT_CPU_TO_CPU_CACHED_READONLY_ADDRESS( buffers[0].buffer );

	}
	else if( format.basic.formatTag == idWaveFile::FORMAT_XMA2 )
	{
		// BFG's Xbox 360 format. Nothing on PC decodes it, and accepting it ended the
		// session at upload time.
		idLib::Warning( "LoadWav( %s ) : XMA2 is an Xbox 360 format and cannot be played", filename.c_str() );
		FreeData();
		return false;
	}
	else
	{
		idLib::Warning( "LoadWav( %s ) : Unsupported wave format %d", filename.c_str(), format.basic.formatTag );
		FreeData();
		return false;
	}

	wave.Close();

	if( format.basic.formatTag == idWaveFile::FORMAT_EXTENSIBLE )
	{
		// HACK: XAudio2 doesn't really support FORMAT_EXTENSIBLE so we convert it to a basic format after extracting the channel mask
		format.basic.formatTag = format.extra.extensible.subFormat.data1;
	}

	// sanity check...
	assert( buffers[buffers.Num() - 1].numSamples == playBegin + playLength );

	return true;
}

/*
========================
idSoundSampleDecode

One Ogg sample decoding on a job worker. The main thread opened the stream, so the
sample's length, rate and channels are already known and only the PCM is outstanding;
the job writes nothing but the pcm frames and decodedFrames. Whoever waits on the list
owns the rest again.
========================
*/
struct idSoundSampleDecode
{
	stb_vorbis*					vorbis = NULL;		// opened on the main thread, or NULL for the job to open
	byte*						fileData = NULL;
	int							fileLen = 0;
	short*						pcm = NULL;
	unsigned int				capacityFrames = 0;
	int							channels = 0;
	int							sampleRate = 0;
	unsigned int				decodedFrames = 0;
	bool						headerMismatch = false;	// the job's open disagreed with SoundSample_PeekOggInfo
	std::unique_ptr<idJobList>	list;
};

idCVar s_asyncSampleDecode( "s_asyncSampleDecode", "1", CVAR_BOOL, "decode the Ogg samples a level load references on job workers, while the rest of the level loads" );

// Decodes this many samples at once at most; beyond it LoadSample decodes on the
// main thread, which keeps the job queue open for the rest of the level load. A
// finished decode stops counting once LoadSample uploads it (FinishSampleDecodes).
static const int SOUND_SAMPLE_MAX_PENDING_DECODES = 48;
static int soundSamplePendingDecodes = 0;

// One Vorbis frame per call, straight into place: what stb_vorbis_decode_memory loops
// on. Thread-safe: it touches only the stream and the output it is given.
static void SoundSample_DecodeFrames( stb_vorbis* vorbis, const int channels, short* pcm, const unsigned int capacityFrames, unsigned int& decodedFrames )
{
	decodedFrames = 0;
	while( decodedFrames < capacityFrames )
	{
		const int frames = stb_vorbis_get_frame_short_interleaved( vorbis, channels, pcm + ( size_t )decodedFrames * channels,
			static_cast<int>( ( capacityFrames - decodedFrames ) * channels ) );
		if( frames <= 0 )
		{
			break;
		}
		decodedFrames += static_cast<unsigned int>( frames );
	}
}

/*
========================
SoundSample_PeekOggInfo

The channels and rate from the identification header and the length from the
end-of-stream page's granule position, without stb_vorbis's codebook setup (about
0.3 ms a file, most of what LoadSample spent on the main thread). The job's own open
checks all three, so a stream this misreads loads the ordinary way.
========================
*/
static uint32 SoundSample_ReadLE32( const byte* p )
{
	return ( uint32 )p[0] | ( ( uint32 )p[1] << 8 ) | ( ( uint32 )p[2] << 16 ) | ( ( uint32 )p[3] << 24 );
}

static bool SoundSample_PeekOggInfo( const byte* data, const int length, int& channels, int& sampleRate, unsigned int& frames )
{
	if( data == NULL || length < 58 || memcmp( data, "OggS", 4 ) != 0 )
	{
		return false;
	}
	const int firstPacket = 27 + data[26];
	if( firstPacket + 16 > length || data[firstPacket] != 0x01 || memcmp( data + firstPacket + 1, "vorbis", 6 ) != 0 )
	{
		return false;
	}
	channels = data[firstPacket + 11];
	sampleRate = static_cast<int>( SoundSample_ReadLE32( data + firstPacket + 12 ) );

	// the last page: flagged end-of-stream and ending exactly at the end of the file
	const int earliest = Max( 0, length - 65536 - 27 );
	for( int page = length - 27; page >= earliest; page-- )
	{
		if( data[page] != 'O' || memcmp( data + page, "OggS", 4 ) != 0 || data[page + 4] != 0 || ( data[page + 5] & 0x04 ) == 0 )
		{
			continue;
		}
		const int segments = data[page + 26];
		if( page + 27 + segments > length )
		{
			continue;
		}
		int pageLength = 27 + segments;
		for( int segment = 0; segment < segments; segment++ )
		{
			pageLength += data[page + 27 + segment];
		}
		if( page + pageLength != length )
		{
			continue;
		}
		const uint32 granuleLow = SoundSample_ReadLE32( data + page + 6 );
		const uint32 granuleHigh = SoundSample_ReadLE32( data + page + 10 );
		if( granuleHigh != 0 || granuleLow == 0 || granuleLow == 0xffffffff )
		{
			return false;
		}
		frames = granuleLow;
		return true;
	}
	return false;
}

// Opens the stream if the main thread did not, decodes it and releases the stream and
// the file bytes. Runs on a worker, or inline.
static void SoundSample_RunDecode( idSoundSampleDecode& decode )
{
	if( decode.vorbis == NULL && decode.fileData != NULL && !decode.headerMismatch )
	{
		int vorbisError = 0;
		decode.vorbis = stb_vorbis_open_memory( decode.fileData, decode.fileLen, &vorbisError, NULL );
		if( decode.vorbis != NULL )
		{
			const stb_vorbis_info info = stb_vorbis_get_info( decode.vorbis );
			if( info.channels != decode.channels || static_cast<int>( info.sample_rate ) != decode.sampleRate ||
					stb_vorbis_stream_length_in_samples( decode.vorbis ) != decode.capacityFrames )
			{
				decode.headerMismatch = true;
				stb_vorbis_close( decode.vorbis );
				decode.vorbis = NULL;
			}
		}
		else
		{
			decode.headerMismatch = true;
		}
	}
	if( decode.vorbis != NULL )
	{
		SoundSample_DecodeFrames( decode.vorbis, decode.channels, decode.pcm, decode.capacityFrames, decode.decodedFrames );
		stb_vorbis_close( decode.vorbis );
		decode.vorbis = NULL;
	}
	if( decode.fileData != NULL )
	{
		Mem_Free( decode.fileData );
		decode.fileData = NULL;
	}
}

static void SoundSample_DecodeJob( const idJobContext& context )
{
	SoundSample_RunDecode( *static_cast<idSoundSampleDecode*>( context.data ) );
}

/*
========================
idSoundSample_OpenAL::BeginOggLoad

Reads the file, opens the stream and sizes the sample from it. With asyncDecode the
PCM is decoded on a job worker and *asyncDecode receives the job (NULL when it was
decoded here after all); without it the whole sample is decoded here.
========================
*/
bool idSoundSample_OpenAL::BeginOggLoad( const idStr& filename, idSoundSampleDecode** asyncDecode )
{
	if( asyncDecode != NULL )
	{
		*asyncDecode = NULL;
	}
	idFileLocal fileIn( fileSystem->OpenFileRead( filename ) );
	if( fileIn == NULL )
	{
		return false;
	}

	const int fileLen = fileIn->Length();
	if( fileLen <= 0 )
	{
		return false;
	}

	byte* fileData = ( byte* )Mem_Alloc( fileLen );
	if( fileData == NULL )
	{
		return false;
	}

	const int bytesRead = fileIn->Read( fileData, fileLen );
	if( bytesRead != fileLen )
	{
		Mem_Free( fileData );
		return false;
	}

	timestamp = fileIn->Timestamp();

	idStr ampName = filename;
	ampName.SetFileExtension( "amp" );
	LoadAmplitude( ampName );

	// Off the main thread entirely when the headers say enough to size the sample.
	int peekChannels = 0;
	int peekRate = 0;
	unsigned int peekFrames = 0;
	if( asyncDecode != NULL && soundSamplePendingDecodes < SOUND_SAMPLE_MAX_PENDING_DECODES &&
			jobSystem.IsInitialized() && !jobSystem.IsSynchronous() &&
			SoundSample_PeekOggInfo( fileData, fileLen, peekChannels, peekRate, peekFrames ) &&
			peekChannels >= 1 && peekChannels <= 2 && peekRate > 0 &&
			( uint64 )peekFrames * peekChannels * sizeof( int16 ) <= ( uint64 )idMath::INT_MAX )
	{
		const int peekBytes = static_cast<int>( ( uint64 )peekFrames * peekChannels * sizeof( int16 ) );
		buffers.SetNum( 1 );
		buffers[0].buffer = AllocBuffer( peekBytes, GetName() );
		if( buffers[0].buffer != NULL )
		{
			FinishOggLoad( peekChannels, peekRate, peekFrames );
			idSoundSampleDecode* decode = new idSoundSampleDecode;
			decode->fileData = fileData;
			decode->fileLen = fileLen;
			decode->pcm = static_cast<short*>( buffers[0].buffer );
			decode->capacityFrames = peekFrames;
			decode->channels = peekChannels;
			decode->sampleRate = peekRate;
			decode->list = jobSystem.CreateJobList( "sound-sample-decode", 1, 0, idJobPriority::LOW );
			if( decode->list != nullptr && decode->list->AddJob( &SoundSample_DecodeJob, decode ) &&
					decode->list->Submit() == idJobSubmitResult::ACCEPTED )
			{
				soundSamplePendingDecodes++;
				*asyncDecode = decode;
				return true;
			}
			if( decode->list != nullptr )
			{
				decode->list->Wait();
			}
			SoundSample_RunDecode( *decode );
			const bool mismatch = decode->headerMismatch;
			const unsigned int decodedFrames = decode->decodedFrames;
			delete decode;
			if( mismatch )
			{
				FreeData();
				return false;
			}
			return FinishOggDecode( filename, decodedFrames );
		}
		buffers.Clear();
	}

	// Open the stream, size the buffer from its length and decode straight into it.
	// stb_vorbis_decode_memory grew a scratch buffer by doubling and then copied it: two
	// to three times a sound's PCM at peak, and a full copy of every sound loaded.
	int vorbisError = 0;
	stb_vorbis* vorbis = stb_vorbis_open_memory( fileData, fileLen, &vorbisError, NULL );
	if( vorbis == NULL )
	{
		Mem_Free( fileData );
		idLib::Warning( "LoadOgg( %s ) : failed to open Ogg Vorbis (stb_vorbis error %d)", filename.c_str(), vorbisError );
		FreeData();
		return false;
	}
	const stb_vorbis_info info = stb_vorbis_get_info( vorbis );
	const int channels = info.channels;
	const int sampleRate = static_cast<int>( info.sample_rate );
	unsigned int streamFrames = stb_vorbis_stream_length_in_samples( vorbis );
	if( streamFrames == 0 && channels >= 1 && channels <= 2 && sampleRate > 0 )
	{
		// No length in the last page: decode the old way, growing a scratch buffer.
		stb_vorbis_close( vorbis );
		int scratchChannels = 0;
		int scratchRate = 0;
		short* scratch = NULL;
		const int scratchFrames = stb_vorbis_decode_memory( fileData, fileLen, &scratchChannels, &scratchRate, &scratch );
		Mem_Free( fileData );
		if( scratchFrames <= 0 || scratch == NULL || scratchChannels != channels ||
				( uint64 )scratchFrames * channels * sizeof( int16 ) > ( uint64 )idMath::INT_MAX )
		{
			free( scratch );
			idLib::Warning( "LoadOgg( %s ) : failed to decode Ogg Vorbis", filename.c_str() );
			FreeData();
			return false;
		}
		streamFrames = static_cast<unsigned int>( scratchFrames );
		const int scratchBytes = static_cast<int>( ( uint64 )streamFrames * channels * sizeof( int16 ) );
		buffers.SetNum( 1 );
		buffers[0].buffer = AllocBuffer( scratchBytes, GetName() );
		if( buffers[0].buffer == NULL )
		{
			free( scratch );
			idLib::Warning( "LoadOgg( %s ) : could not allocate decoded audio", filename.c_str() );
			FreeData();
			return false;
		}
		memcpy( buffers[0].buffer, scratch, scratchBytes );
		free( scratch );
		return FinishOggLoad( channels, sampleRate, streamFrames );
	}
	if( channels < 1 || channels > 2 || sampleRate <= 0 || streamFrames == 0 ||
			( uint64 )streamFrames * channels * sizeof( int16 ) > ( uint64 )idMath::INT_MAX )
	{
		stb_vorbis_close( vorbis );
		Mem_Free( fileData );
		idLib::Warning( "LoadOgg( %s ) : unsupported stream (%d channels, %d Hz, %u frames)", filename.c_str(), channels, sampleRate, streamFrames );
		FreeData();
		return false;
	}

	const int capacityBytes = static_cast<int>( ( uint64 )streamFrames * channels * sizeof( int16 ) );
	buffers.SetNum( 1 );
	buffers[0].buffer = AllocBuffer( capacityBytes, GetName() );
	if( buffers[0].buffer == NULL )
	{
		stb_vorbis_close( vorbis );
		Mem_Free( fileData );
		idLib::Warning( "LoadOgg( %s ) : could not allocate decoded audio", filename.c_str() );
		FreeData();
		return false;
	}
	// Sized from the stream, so the length, rate and channels hold from here on.
	FinishOggLoad( channels, sampleRate, streamFrames );

	idSoundSampleDecode* decode = new idSoundSampleDecode;
	decode->vorbis = vorbis;
	decode->fileData = fileData;
	decode->fileLen = fileLen;
	decode->sampleRate = sampleRate;
	decode->pcm = static_cast<short*>( buffers[0].buffer );
	decode->capacityFrames = streamFrames;
	decode->channels = channels;

	if( asyncDecode != NULL && soundSamplePendingDecodes < SOUND_SAMPLE_MAX_PENDING_DECODES &&
			jobSystem.IsInitialized() && !jobSystem.IsSynchronous() )
	{
		decode->list = jobSystem.CreateJobList( "sound-sample-decode", 1, 0, idJobPriority::LOW );
		if( decode->list != nullptr && decode->list->AddJob( &SoundSample_DecodeJob, decode ) &&
				decode->list->Submit() == idJobSubmitResult::ACCEPTED )
		{
			soundSamplePendingDecodes++;
			*asyncDecode = decode;
			return true;
		}
		// rejected or run inline by the job system: finish below
		if( decode->list != nullptr )
		{
			decode->list->Wait();
		}
	}

	SoundSample_RunDecode( *decode );
	const unsigned int decodedFrames = decode->decodedFrames;
	delete decode;
	return FinishOggDecode( filename, decodedFrames );
}

/*
========================
idSoundSample_OpenAL::FinishOggDecode

The stream's PCM is in buffers[0]. A stream that decodes short keeps what it had.
========================
*/
bool idSoundSample_OpenAL::FinishOggDecode( const idStr& filename, const unsigned int decodedFrames )
{
	if( decodedFrames == 0 )
	{
		idLib::Warning( "LoadOgg( %s ) : failed to decode Ogg Vorbis", filename.c_str() );
		FreeData();
		return false;
	}
	if( decodedFrames < static_cast<unsigned int>( playLength ) )
	{
		// stb_vorbis stops at the first page it cannot decode and keeps what it has
		idLib::Warning( "LoadOgg( %s ) : decoded %u of %d frames; the file is damaged and plays short", filename.c_str(), decodedFrames, playLength );
		return FinishOggLoad( NumChannels(), SampleRate(), decodedFrames );
	}
	return true;
}

/*
========================
idSoundSample_OpenAL::LoadOgg
========================
*/
bool idSoundSample_OpenAL::LoadOgg( const idStr& filename )
{
	return BeginOggLoad( filename, NULL );
}

/*
========================
idSoundSample_OpenAL::LoadResourceAsync

LoadResource for a level load: when the first sample the probe would try is an Ogg,
the file is read and opened here and its PCM decodes on a job worker while the level
keeps loading. Length, rate and channels hold at once; FinishDecode waits for the PCM
and uploads it, and every reader of the PCM calls it first. Anything else, and any
failure, takes the normal synchronous probe.
========================
*/
void idSoundSample_OpenAL::LoadResourceAsync()
{
	FinishDecode();
	if( !s_asyncSampleDecode.GetBool() || s_noSound.GetBool() || idStr::Icmpn( GetName(), "_default", 8 ) == 0 )
	{
		LoadResource();
		return;
	}

	idList< idStr > sampleVariants;
	SoundSample_BuildVariants( GetName(), sampleVariants );
	idStr oggName = sampleVariants.Num() > 0 ? sampleVariants[0] : idStr( GetName() );
	idStr ext;
	oggName.ExtractFileExtension( ext );
	if( ext.Icmp( "roq" ) == 0 )
	{
		LoadResource();
		return;
	}
	oggName.SetFileExtension( ".ogg" );

	FreeData();
	idSoundSampleDecode* decode = NULL;
	if( !BeginOggLoad( oggName, &decode ) )
	{
		// no Ogg first, or a broken one: the normal probe tries every loader and variant
		LoadResource();
		return;
	}
	loaded = true;
	if( decode == NULL )
	{
		CreateOpenALBuffer();
		return;
	}
	pendingDecode = decode;
	pendingDecodeName = oggName;
}

/*
========================
idSoundSample_OpenAL::FinishDecode

Waits for an outstanding decode and uploads the sample. Does nothing without one.
========================
*/
void idSoundSample_OpenAL::FinishDecode()
{
	if( pendingDecode == NULL )
	{
		return;
	}
	idSoundSampleDecode* decode = pendingDecode;
	pendingDecode = NULL;
	soundSamplePendingDecodes--;
	if( decode->list != nullptr )
	{
		decode->list->Wait();
	}
	// a cancelled job never ran: decode it here
	SoundSample_RunDecode( *decode );
	const bool mismatch = decode->headerMismatch;
	const unsigned int decodedFrames = decode->decodedFrames;
	delete decode;

	if( mismatch )
	{
		// the peeked header disagreed with the stream: load it the ordinary way
		LoadResource();
		return;
	}
	if( !FinishOggDecode( pendingDecodeName, decodedFrames ) )
	{
		// the normal probe falls back to other loaders, variants and the default
		LoadResource();
		return;
	}
	CreateOpenALBuffer();
}

/*
========================
idSoundSample_OpenAL::IsDecodeComplete
========================
*/
bool idSoundSample_OpenAL::IsDecodeComplete() const
{
	return pendingDecode != NULL && ( pendingDecode->list == nullptr || pendingDecode->list->TryWait() );
}

/*
========================
idSoundSample_OpenAL::CancelDecode

Waits for an outstanding decode and drops it; the caller frees the sample.
========================
*/
void idSoundSample_OpenAL::CancelDecode()
{
	if( pendingDecode == NULL )
	{
		return;
	}
	idSoundSampleDecode* decode = pendingDecode;
	pendingDecode = NULL;
	soundSamplePendingDecodes--;
	if( decode->list != nullptr )
	{
		decode->list->Cancel();
		decode->list->Wait();
	}
	if( decode->vorbis != NULL )
	{
		stb_vorbis_close( decode->vorbis );
		decode->vorbis = NULL;
	}
	if( decode->fileData != NULL )
	{
		Mem_Free( decode->fileData );
		decode->fileData = NULL;
	}
	delete decode;
}

/*
========================
idSoundSample_OpenAL::FinishOggLoad

buffers[0] holds frames of interleaved 16-bit PCM.
========================
*/
bool idSoundSample_OpenAL::FinishOggLoad( const int channels, const int sampleRate, const unsigned int frames )
{
	memset( &format, 0, sizeof( format ) );
	format.basic.formatTag = idWaveFile::FORMAT_PCM;
	format.basic.numChannels = ( uint16 )channels;
	format.basic.samplesPerSec = sampleRate;
	format.basic.bitsPerSample = 16;
	format.basic.blockSize = format.basic.numChannels * format.basic.bitsPerSample / 8;
	format.basic.avgBytesPerSec = format.basic.samplesPerSec * format.basic.blockSize;

	playBegin = 0;
	playLength = static_cast<int>( frames );
	totalBufferSize = static_cast<int>( ( uint64 )frames * channels * sizeof( int16 ) );
	buffers[0].bufferSize = totalBufferSize;
	buffers[0].numSamples = playLength;
	buffers[0].buffer = GPU_CONVERT_CPU_TO_CPU_CACHED_READONLY_ADDRESS( buffers[0].buffer );

	return true;
}

/*
========================
idSoundSample_OpenAL::LoadRoQ
========================
*/
bool idSoundSample_OpenAL::LoadRoQ( const idStr& filename )
{
	idFileLocal fileIn( fileSystem->OpenFileRead( filename ) );
	if( fileIn == NULL )
	{
		return false;
	}

	const int fileLen = fileIn->Length();
	if( fileLen < 16 )
	{
		return false;
	}

	byte* fileData = ( byte* )Mem_Alloc( fileLen );
	if( fileData == NULL )
	{
		return false;
	}

	const int bytesRead = fileIn->Read( fileData, fileLen );
	if( bytesRead != fileLen )
	{
		Mem_Free( fileData );
		return false;
	}

	const int roqMagic = fileData[0] | ( fileData[1] << 8 );
	if( roqMagic != ROQ_FILE_MAGIC )
	{
		Mem_Free( fileData );
		return false;
	}

	timestamp = fileIn->Timestamp();

	idStr ampName = filename;
	ampName.SetFileExtension( "amp" );
	LoadAmplitude( ampName );

	int channels = 0;
	idList<int16> pcmSamples;
	pcmSamples.SetGranularity( 4096 );

	int offset = 8;
	while( offset + 8 <= fileLen )
	{
		const int chunkId = fileData[offset + 0] | ( fileData[offset + 1] << 8 );
		const int chunkSize = fileData[offset + 2] | ( fileData[offset + 3] << 8 ) | ( fileData[offset + 4] << 16 );
		const int chunkArg = fileData[offset + 6] | ( fileData[offset + 7] << 8 );

		offset += 8;

		if( chunkSize > fileLen - offset )
		{
			Mem_Free( fileData );
			idLib::Warning( "LoadRoQ( %s ) : truncated audio chunk", filename.c_str() );
			return false;
		}

		const byte* chunkData = fileData + offset;

		if( chunkId == ROQ_SOUND_MONO )
		{
			if( channels == 0 )
			{
				channels = 1;
			}
			else if( channels != 1 )
			{
				Mem_Free( fileData );
				idLib::Warning( "LoadRoQ( %s ) : mixed mono/stereo RoQ audio chunks", filename.c_str() );
				return false;
			}

			const int oldSamples = pcmSamples.Num();
			if( chunkSize > idMath::INT_MAX - oldSamples )
			{
				Mem_Free( fileData );
				idLib::Warning( "LoadRoQ( %s ) : decoded audio is too large", filename.c_str() );
				return false;
			}
			pcmSamples.SetNum( oldSamples + chunkSize );

			int32 predictor = static_cast<int16>( chunkArg );
			for( int i = 0; i < chunkSize; ++i )
			{
				predictor += RoQAudioDelta( chunkData[i] );
				predictor = idMath::ClampInt( ROQ_AUDIO_MIN_SAMPLE, ROQ_AUDIO_MAX_SAMPLE, predictor );
				pcmSamples[ oldSamples + i ] = static_cast<int16>( predictor );
			}
		}
		else if( chunkId == ROQ_SOUND_STEREO )
		{
			if( ( chunkSize & 1 ) != 0 )
			{
				Mem_Free( fileData );
				idLib::Warning( "LoadRoQ( %s ) : malformed stereo audio chunk", filename.c_str() );
				return false;
			}
			if( channels == 0 )
			{
				channels = 2;
			}
			else if( channels != 2 )
			{
				Mem_Free( fileData );
				idLib::Warning( "LoadRoQ( %s ) : mixed mono/stereo RoQ audio chunks", filename.c_str() );
				return false;
			}

			const int stereoBytes = chunkSize & ~1;
			const int samplePairs = stereoBytes >> 1;
			const int oldSamples = pcmSamples.Num();
			if( stereoBytes > idMath::INT_MAX - oldSamples )
			{
				Mem_Free( fileData );
				idLib::Warning( "LoadRoQ( %s ) : decoded audio is too large", filename.c_str() );
				return false;
			}
			pcmSamples.SetNum( oldSamples + samplePairs * 2 );

			int32 leftPredictor = static_cast<int16>( chunkArg & 0xFF00 );
			int32 rightPredictor = static_cast<int16>( ( chunkArg & 0x00FF ) << 8 );
			int outIndex = oldSamples;

			for( int i = 0; i < stereoBytes; i += 2 )
			{
				leftPredictor += RoQAudioDelta( chunkData[i + 0] );
				rightPredictor += RoQAudioDelta( chunkData[i + 1] );
				leftPredictor = idMath::ClampInt( ROQ_AUDIO_MIN_SAMPLE, ROQ_AUDIO_MAX_SAMPLE, leftPredictor );
				rightPredictor = idMath::ClampInt( ROQ_AUDIO_MIN_SAMPLE, ROQ_AUDIO_MAX_SAMPLE, rightPredictor );

				pcmSamples[ outIndex++ ] = static_cast<int16>( leftPredictor );
				pcmSamples[ outIndex++ ] = static_cast<int16>( rightPredictor );
			}
		}

		offset += chunkSize;
	}

	Mem_Free( fileData );

	if( channels == 0 || pcmSamples.Num() == 0 )
	{
		return false;
	}

	memset( &format, 0, sizeof( format ) );
	format.basic.formatTag = idWaveFile::FORMAT_PCM;
	format.basic.numChannels = static_cast<uint16>( channels );
	format.basic.samplesPerSec = ROQ_AUDIO_SAMPLE_RATE;
	format.basic.bitsPerSample = 16;
	format.basic.blockSize = static_cast<uint16>( format.basic.numChannels * format.basic.bitsPerSample / 8 );
	format.basic.avgBytesPerSec = format.basic.samplesPerSec * format.basic.blockSize;

	playBegin = 0;
	playLength = pcmSamples.Num() / channels;
	if( pcmSamples.Num() > idMath::INT_MAX / ( int )sizeof( int16 ) )
	{
		idLib::Warning( "LoadRoQ( %s ) : decoded audio is too large", filename.c_str() );
		return false;
	}
	totalBufferSize = pcmSamples.Num() * sizeof( int16 );

	buffers.SetNum( 1 );
	buffers[0].bufferSize = totalBufferSize;
	buffers[0].numSamples = playLength;
	buffers[0].buffer = AllocBuffer( totalBufferSize, GetName() );
	if( buffers[0].buffer == NULL )
	{
		idLib::Warning( "LoadRoQ( %s ) : could not allocate decoded audio", filename.c_str() );
		return false;
	}
	memcpy( buffers[0].buffer, pcmSamples.Ptr(), totalBufferSize );
	buffers[0].buffer = GPU_CONVERT_CPU_TO_CPU_CACHED_READONLY_ADDRESS( buffers[0].buffer );

	return true;
}


/*
========================
idSoundSample_OpenAL::MakeDefault
========================
*/
void idSoundSample_OpenAL::MakeDefault()
{
	FreeData();

	static const int DEFAULT_NUM_SAMPLES = 4096;

	timestamp = FILE_NOT_FOUND_TIMESTAMP;
	loaded = true;

	memset( &format, 0, sizeof( format ) );
	format.basic.formatTag = idWaveFile::FORMAT_PCM;
	format.basic.numChannels = 1;
	format.basic.bitsPerSample = 16;
	format.basic.samplesPerSec = 22050; //44100; //XAUDIO2_MIN_SAMPLE_RATE;
	format.basic.blockSize = format.basic.numChannels * format.basic.bitsPerSample / 8;
	format.basic.avgBytesPerSec = format.basic.samplesPerSec * format.basic.blockSize;

	assert( format.basic.blockSize == 2 );

	totalBufferSize = DEFAULT_NUM_SAMPLES * 2;// * sizeof( short );

	short* defaultBuffer = ( short* )AllocBuffer( totalBufferSize, GetName() );
	for( int i = 0; i < DEFAULT_NUM_SAMPLES; i += 2 )
	{
		float v = sin( idMath::PI * 2 * i / 64 );
		int sample = v * 0x4000;
		defaultBuffer[i + 0] = sample;
		defaultBuffer[i + 1] = sample;

		//defaultBuffer[i + 0] = SHRT_MIN;
		//defaultBuffer[i + 1] = SHRT_MAX;
	}

	buffers.SetNum( 1 );
	buffers[0].buffer = defaultBuffer;
	buffers[0].bufferSize = totalBufferSize;
	buffers[0].numSamples = DEFAULT_NUM_SAMPLES;
	buffers[0].buffer = GPU_CONVERT_CPU_TO_CPU_CACHED_READONLY_ADDRESS( buffers[0].buffer );

	playBegin = 0;
	playLength = DEFAULT_NUM_SAMPLES;

	CreateOpenALBuffer();
}

/*
========================
idSoundSample_OpenAL::FreeData

Called before deleting the object and at the start of LoadResource()
========================
*/
void idSoundSample_OpenAL::FreeData()
{
	// a worker may still be writing into buffers[0]
	CancelDecode();
	if( buffers.Num() > 0 || openalBuffer != 0 )
	{
		soundSystemLocal.StopVoicesWithSample( ( idSoundSample* )this );
	}
	if( buffers.Num() > 0 )
	{
		for( int i = 0; i < buffers.Num(); i++ )
		{
			FreeBuffer( buffers[i].buffer );
		}
		buffers.Clear();
	}
	amplitude.Clear();

	timestamp = FILE_NOT_FOUND_TIMESTAMP;
	memset( &format, 0, sizeof( format ) );
	loaded = false;
	totalBufferSize = 0;
	payloadReleased = false;
	playBegin = 0;
	playLength = 0;
	openalBufferUploadFailed = false;

	if( openalBuffer != 0 )
	{
		if( soundSystemLocal.hardware.openalContext == NULL || alcGetCurrentContext() != soundSystemLocal.hardware.openalContext )
		{
			openalBuffer = 0;
			return;
		}

		alGetError(); // clear any existing error
		if( alIsBuffer( openalBuffer ) )
		{
			alDeleteBuffers( 1, &openalBuffer );
			ALenum err = alGetError();
			if( err != AL_NO_ERROR && err != AL_INVALID_NAME )
			{
				common->Warning( "idSoundSample_OpenAL::FreeData: error unloading OpenAL buffer (0x%x)", err );
			}
		}
		openalBuffer = 0;
	}
}

/*
========================
idSoundSample_OpenAL::LoadAmplitude
========================
*/
bool idSoundSample_OpenAL::LoadAmplitude( const idStr& name )
{
	amplitude.Clear();
	idFileLocal f( fileSystem->OpenFileRead( name ) );
	if( f == NULL )
	{
		return false;
	}
	const int fileLength = f->Length();
	if( fileLength < 0 )
	{
		return false;
	}
	amplitude.SetNum( fileLength );
	if( !openQ4_ReadExact( f, amplitude.Ptr(), amplitude.Num() ) )
	{
		amplitude.Clear();
		return false;
	}
	return true;
}

/*
========================
idSoundSample_OpenAL::GetAmplitude
========================
*/
float idSoundSample_OpenAL::GetAmplitude( int timeMS ) const
{
	if( timeMS < 0 || timeMS > LengthInMsec() )
	{
		return 0.0f;
	}
	if( IsDefault() )
	{
		return 1.0f;
	}
	int index = timeMS * 60 / 1000;
	if( index < 0 || index >= amplitude.Num() )
	{
		return 0.0f;
	}
	return ( float )amplitude[index] / 255.0f;
}


#if 0 //defined(AL_SOFT_buffer_samples)
const char* idSoundSample_OpenAL::OpenALSoftChannelsName( ALenum chans ) const
{
	switch( chans )
	{
		case AL_MONO_SOFT:
			return "Mono";
		case AL_STEREO_SOFT:
			return "Stereo";
		case AL_REAR_SOFT:
			return "Rear";
		case AL_QUAD_SOFT:
			return "Quadraphonic";
		case AL_5POINT1_SOFT:
			return "5.1 Surround";
		case AL_6POINT1_SOFT:
			return "6.1 Surround";
		case AL_7POINT1_SOFT:
			return "7.1 Surround";
	}

	return "Unknown Channels";
}

const char* idSoundSample_OpenAL::OpenALSoftTypeName( ALenum type ) const
{
	switch( type )
	{
		case AL_BYTE_SOFT:
			return "S8";
		case AL_UNSIGNED_BYTE_SOFT:
			return "U8";
		case AL_SHORT_SOFT:
			return "S16";
		case AL_UNSIGNED_SHORT_SOFT:
			return "U16";
		case AL_INT_SOFT:
			return "S32";
		case AL_UNSIGNED_INT_SOFT:
			return "U32";
		case AL_FLOAT_SOFT:
			return "Float32";
		case AL_DOUBLE_SOFT:
			return "Float64";
	}

	return "Unknown Type";
}

ALsizei idSoundSample_OpenAL::FramesToBytes( ALsizei size, ALenum channels, ALenum type ) const
{
	switch( channels )
	{
		case AL_MONO_SOFT:
			size *= 1;
			break;
		case AL_STEREO_SOFT:
			size *= 2;
			break;
		case AL_REAR_SOFT:
			size *= 2;
			break;
		case AL_QUAD_SOFT:
			size *= 4;
			break;
		case AL_5POINT1_SOFT:
			size *= 6;
			break;
		case AL_6POINT1_SOFT:
			size *= 7;
			break;
		case AL_7POINT1_SOFT:
			size *= 8;
			break;
	}

	switch( type )
	{
		case AL_BYTE_SOFT:
			size *= sizeof( ALbyte );
			break;
		case AL_UNSIGNED_BYTE_SOFT:
			size *= sizeof( ALubyte );
			break;
		case AL_SHORT_SOFT:
			size *= sizeof( ALshort );
			break;
		case AL_UNSIGNED_SHORT_SOFT:
			size *= sizeof( ALushort );
			break;
		case AL_INT_SOFT:
			size *= sizeof( ALint );
			break;
		case AL_UNSIGNED_INT_SOFT:
			size *= sizeof( ALuint );
			break;
		case AL_FLOAT_SOFT:
			size *= sizeof( ALfloat );
			break;
		case AL_DOUBLE_SOFT:
			size *= sizeof( ALdouble );
			break;
	}

	return size;
}

ALsizei idSoundSample_OpenAL::BytesToFrames( ALsizei size, ALenum channels, ALenum type ) const
{
	return size / FramesToBytes( 1, channels, type );
}

ALenum idSoundSample_OpenAL::GetOpenALSoftFormat( ALenum channels, ALenum type ) const
{
	ALenum format = AL_NONE;

	/* If using AL_SOFT_buffer_samples, try looking through its formats */
	if( alIsExtensionPresent( "AL_SOFT_buffer_samples" ) )
	{
		/* AL_SOFT_buffer_samples is more lenient with matching formats. The
		 * specified sample type does not need to match the returned format,
		 * but it is nice to try to get something close. */
		if( type == AL_UNSIGNED_BYTE_SOFT || type == AL_BYTE_SOFT )
		{
			if( channels == AL_MONO_SOFT )
			{
				format = AL_MONO8_SOFT;
			}
			else if( channels == AL_STEREO_SOFT )
			{
				format = AL_STEREO8_SOFT;
			}
			else if( channels == AL_QUAD_SOFT )
			{
				format = AL_QUAD8_SOFT;
			}
			else if( channels == AL_5POINT1_SOFT )
			{
				format = AL_5POINT1_8_SOFT;
			}
			else if( channels == AL_6POINT1_SOFT )
			{
				format = AL_6POINT1_8_SOFT;
			}
			else if( channels == AL_7POINT1_SOFT )
			{
				format = AL_7POINT1_8_SOFT;
			}
		}
		else if( type == AL_UNSIGNED_SHORT_SOFT || type == AL_SHORT_SOFT )
		{
			if( channels == AL_MONO_SOFT )
			{
				format = AL_MONO16_SOFT;
			}
			else if( channels == AL_STEREO_SOFT )
			{
				format = AL_STEREO16_SOFT;
			}
			else if( channels == AL_QUAD_SOFT )
			{
				format = AL_QUAD16_SOFT;
			}
			else if( channels == AL_5POINT1_SOFT )
			{
				format = AL_5POINT1_16_SOFT;
			}
			else if( channels == AL_6POINT1_SOFT )
			{
				format = AL_6POINT1_16_SOFT;
			}
			else if( channels == AL_7POINT1_SOFT )
			{
				format = AL_7POINT1_16_SOFT;
			}
		}
		else if( type == AL_UNSIGNED_BYTE3_SOFT || type == AL_BYTE3_SOFT ||
				 type == AL_UNSIGNED_INT_SOFT || type == AL_INT_SOFT ||
				 type == AL_FLOAT_SOFT || type == AL_DOUBLE_SOFT )
		{
			if( channels == AL_MONO_SOFT )
			{
				format = AL_MONO32F_SOFT;
			}
			else if( channels == AL_STEREO_SOFT )
			{
				format = AL_STEREO32F_SOFT;
			}
			else if( channels == AL_QUAD_SOFT )
			{
				format = AL_QUAD32F_SOFT;
			}
			else if( channels == AL_5POINT1_SOFT )
			{
				format = AL_5POINT1_32F_SOFT;
			}
			else if( channels == AL_6POINT1_SOFT )
			{
				format = AL_6POINT1_32F_SOFT;
			}
			else if( channels == AL_7POINT1_SOFT )
			{
				format = AL_7POINT1_32F_SOFT;
			}
		}

		if( format != AL_NONE && !alIsBufferFormatSupportedSOFT( format ) )
		{
			format = AL_NONE;
		}

		/* A matching format was not found or supported. Try 32-bit float. */
		if( format == AL_NONE )
		{
			if( channels == AL_MONO_SOFT )
			{
				format = AL_MONO32F_SOFT;
			}
			else if( channels == AL_STEREO_SOFT )
			{
				format = AL_STEREO32F_SOFT;
			}
			else if( channels == AL_QUAD_SOFT )
			{
				format = AL_QUAD32F_SOFT;
			}
			else if( channels == AL_5POINT1_SOFT )
			{
				format = AL_5POINT1_32F_SOFT;
			}
			else if( channels == AL_6POINT1_SOFT )
			{
				format = AL_6POINT1_32F_SOFT;
			}
			else if( channels == AL_7POINT1_SOFT )
			{
				format = AL_7POINT1_32F_SOFT;
			}

			if( format != AL_NONE && !alIsBufferFormatSupportedSOFT( format ) )
			{
				format = AL_NONE;
			}
		}
		/* 32-bit float not supported. Try 16-bit int. */
		if( format == AL_NONE )
		{
			if( channels == AL_MONO_SOFT )
			{
				format = AL_MONO16_SOFT;
			}
			else if( channels == AL_STEREO_SOFT )
			{
				format = AL_STEREO16_SOFT;
			}
			else if( channels == AL_QUAD_SOFT )
			{
				format = AL_QUAD16_SOFT;
			}
			else if( channels == AL_5POINT1_SOFT )
			{
				format = AL_5POINT1_16_SOFT;
			}
			else if( channels == AL_6POINT1_SOFT )
			{
				format = AL_6POINT1_16_SOFT;
			}
			else if( channels == AL_7POINT1_SOFT )
			{
				format = AL_7POINT1_16_SOFT;
			}

			if( format != AL_NONE && !alIsBufferFormatSupportedSOFT( format ) )
			{
				format = AL_NONE;
			}
		}
		/* 16-bit int not supported. Try 8-bit int. */
		if( format == AL_NONE )
		{
			if( channels == AL_MONO_SOFT )
			{
				format = AL_MONO8_SOFT;
			}
			else if( channels == AL_STEREO_SOFT )
			{
				format = AL_STEREO8_SOFT;
			}
			else if( channels == AL_QUAD_SOFT )
			{
				format = AL_QUAD8_SOFT;
			}
			else if( channels == AL_5POINT1_SOFT )
			{
				format = AL_5POINT1_8_SOFT;
			}
			else if( channels == AL_6POINT1_SOFT )
			{
				format = AL_6POINT1_8_SOFT;
			}
			else if( channels == AL_7POINT1_SOFT )
			{
				format = AL_7POINT1_8_SOFT;
			}

			if( format != AL_NONE && !alIsBufferFormatSupportedSOFT( format ) )
			{
				format = AL_NONE;
			}
		}

		return format;
	}

	/* We use the AL_EXT_MCFORMATS extension to provide output of Quad, 5.1,
	 * and 7.1 channel configs, AL_EXT_FLOAT32 for 32-bit float samples, and
	 * AL_EXT_DOUBLE for 64-bit float samples. */
	if( type == AL_UNSIGNED_BYTE_SOFT )
	{
		if( channels == AL_MONO_SOFT )
		{
			format = AL_FORMAT_MONO8;
		}
		else if( channels == AL_STEREO_SOFT )
		{
			format = AL_FORMAT_STEREO8;
		}
		else if( alIsExtensionPresent( "AL_EXT_MCFORMATS" ) )
		{
			if( channels == AL_QUAD_SOFT )
			{
				format = alGetEnumValue( "AL_FORMAT_QUAD8" );
			}
			else if( channels == AL_5POINT1_SOFT )
			{
				format = alGetEnumValue( "AL_FORMAT_51CHN8" );
			}
			else if( channels == AL_6POINT1_SOFT )
			{
				format = alGetEnumValue( "AL_FORMAT_61CHN8" );
			}
			else if( channels == AL_7POINT1_SOFT )
			{
				format = alGetEnumValue( "AL_FORMAT_71CHN8" );
			}
		}
	}
	else if( type == AL_SHORT_SOFT )
	{
		if( channels == AL_MONO_SOFT )
		{
			format = AL_FORMAT_MONO16;
		}
		else if( channels == AL_STEREO_SOFT )
		{
			format = AL_FORMAT_STEREO16;
		}
		else if( alIsExtensionPresent( "AL_EXT_MCFORMATS" ) )
		{
			if( channels == AL_QUAD_SOFT )
			{
				format = alGetEnumValue( "AL_FORMAT_QUAD16" );
			}
			else if( channels == AL_5POINT1_SOFT )
			{
				format = alGetEnumValue( "AL_FORMAT_51CHN16" );
			}
			else if( channels == AL_6POINT1_SOFT )
			{
				format = alGetEnumValue( "AL_FORMAT_61CHN16" );
			}
			else if( channels == AL_7POINT1_SOFT )
			{
				format = alGetEnumValue( "AL_FORMAT_71CHN16" );
			}
		}
	}
	else if( type == AL_FLOAT_SOFT && alIsExtensionPresent( "AL_EXT_FLOAT32" ) )
	{
		if( channels == AL_MONO_SOFT )
		{
			format = alGetEnumValue( "AL_FORMAT_MONO_FLOAT32" );
		}
		else if( channels == AL_STEREO_SOFT )
		{
			format = alGetEnumValue( "AL_FORMAT_STEREO_FLOAT32" );
		}
		else if( alIsExtensionPresent( "AL_EXT_MCFORMATS" ) )
		{
			if( channels == AL_QUAD_SOFT )
			{
				format = alGetEnumValue( "AL_FORMAT_QUAD32" );
			}
			else if( channels == AL_5POINT1_SOFT )
			{
				format = alGetEnumValue( "AL_FORMAT_51CHN32" );
			}
			else if( channels == AL_6POINT1_SOFT )
			{
				format = alGetEnumValue( "AL_FORMAT_61CHN32" );
			}
			else if( channels == AL_7POINT1_SOFT )
			{
				format = alGetEnumValue( "AL_FORMAT_71CHN32" );
			}
		}
	}
	else if( type == AL_DOUBLE_SOFT && alIsExtensionPresent( "AL_EXT_DOUBLE" ) )
	{
		if( channels == AL_MONO_SOFT )
		{
			format = alGetEnumValue( "AL_FORMAT_MONO_DOUBLE" );
		}
		else if( channels == AL_STEREO_SOFT )
		{
			format = alGetEnumValue( "AL_FORMAT_STEREO_DOUBLE" );
		}
	}

	/* NOTE: It seems OSX returns -1 from alGetEnumValue for unknown enums, as
	 * opposed to 0. Correct it. */
	if( format == -1 )
	{
		format = 0;
	}

	return format;
}
#endif // #if defined(AL_SOFT_buffer_samples)

ALenum idSoundSample_OpenAL::GetOpenALBufferFormat() const
{
	ALenum alFormat;

	if( format.basic.formatTag == idWaveFile::FORMAT_PCM )
	{
		alFormat = NumChannels() == 1 ? AL_FORMAT_MONO16 : AL_FORMAT_STEREO16;
	}
	else if( format.basic.formatTag == idWaveFile::FORMAT_ADPCM )
	{
		//alFormat = NumChannels() == 1 ? AL_FORMAT_MONO8 : AL_FORMAT_STEREO8;
		alFormat = NumChannels() == 1 ? AL_FORMAT_MONO16 : AL_FORMAT_STEREO16;
		//alFormat = NumChannels() == 1 ? AL_FORMAT_MONO_IMA4 : AL_FORMAT_STEREO_IMA4;
	}
	else if( format.basic.formatTag == idWaveFile::FORMAT_XMA2 )
	{
		alFormat = NumChannels() == 1 ? AL_FORMAT_MONO16 : AL_FORMAT_STEREO16;
	}
	else
	{
		alFormat = NumChannels() == 1 ? AL_FORMAT_MONO16 : AL_FORMAT_STEREO16;
	}

	return alFormat;
}

int32 idSoundSample_OpenAL::MS_ADPCM_nibble( MS_ADPCM_decodeState_t* state, int8 nybble )
{
	const int32 max_audioval = ( ( 1 << ( 16 - 1 ) ) - 1 );
	const int32 min_audioval = -( 1 << ( 16 - 1 ) );
	const int32 adaptive[] =
	{
		230, 230, 230, 230, 307, 409, 512, 614,
		768, 614, 512, 409, 307, 230, 230, 230
	};

	int32 delta;

	int64_t widenedSample =
		( static_cast<int64_t>( state->iSamp1 ) * state->coef1 +
			static_cast<int64_t>( state->iSamp2 ) * state->coef2 ) / 256;

	if( nybble & 0x08 )
	{
		widenedSample += static_cast<int64_t>( state->iDelta ) * ( nybble - 0x10 );
	}
	else
	{
		widenedSample += static_cast<int64_t>( state->iDelta ) * nybble;
	}

	if( widenedSample < min_audioval )
	{
		widenedSample = min_audioval;
	}
	else if( widenedSample > max_audioval )
	{
		widenedSample = max_audioval;
	}
	const int32 new_sample = static_cast<int32>( widenedSample );

	delta = ( ( int32 ) state->iDelta * adaptive[nybble] ) / 256;
	if( delta < 16 )
	{
		delta = 16;
	}

	state->iDelta = ( uint16 ) delta;
	state->iSamp2 = state->iSamp1;
	state->iSamp1 = ( int16 ) new_sample;

	return ( new_sample );
}

int idSoundSample_OpenAL::MS_ADPCM_decode( uint8** audio_buf, uint32* audio_len )
{
	static MS_ADPCM_decodeState_t	states[2];
	MS_ADPCM_decodeState_t*			state[2];

	uint8* encoded;
	uint8* decoded;
	uint32_t encoded_len;
	int32 samplesleft;
	int8 nybble;
	int8 stereo;
	int32 new_sample;

	if( audio_buf == NULL || audio_len == NULL || *audio_buf == NULL )
	{
		return -1;
	}

	size_t decodedBytes = 0;
	if( !openQ4_GetMSADPCMDecodedSize( *audio_len, format.basic.blockSize,
		format.extra.adpcm.samplesPerBlock, format.basic.numChannels,
		format.extra.adpcm.numCoef, decodedBytes ) )
	{
		return -1;
	}

	uint8* const originalBuffer = *audio_buf;
	encoded_len = *audio_len;
	encoded = *audio_buf;

	// Validate every block's coefficient selector before allocating or decoding.
	for( uint32_t blockOffset = 0; blockOffset < encoded_len; blockOffset += format.basic.blockSize )
	{
		for( uint16_t channel = 0; channel < format.basic.numChannels; ++channel )
		{
			const uint8_t predictor = encoded[ blockOffset + channel ];
			if( predictor >= format.extra.adpcm.numCoef || predictor >= 7 )
			{
				return -1;
			}
		}
	}

	uint8* const decodedBuffer = static_cast<uint8*>( Mem_Alloc( decodedBytes ) );
	if( decodedBuffer == NULL )
	{
		//SDL_Error( SDL_ENOMEM );
		return -1;
	}
	decoded = decodedBuffer;

	assert( format.basic.numChannels == 1 || format.basic.numChannels == 2 );

	// Get ready... Go!
	stereo = ( format.basic.numChannels == 2 ) ? 1 : 0;
	state[0] = &states[0];
	state[1] = &states[stereo];

	while( encoded_len >= format.basic.blockSize )
	{
		// Grab the initial information for this block
		state[0]->hPredictor = *encoded++;

		assert( state[0]->hPredictor < format.extra.adpcm.numCoef );
		state[0]->hPredictor = idMath::ClampInt( 0, 6, state[0]->hPredictor );

		state[0]->coef1 = format.extra.adpcm.aCoef[state[0]->hPredictor].coef1;
		state[0]->coef2 = format.extra.adpcm.aCoef[state[0]->hPredictor].coef2;

		if( stereo )
		{
			state[1]->hPredictor = *encoded++;

			assert( state[1]->hPredictor < format.extra.adpcm.numCoef );
			state[1]->hPredictor = idMath::ClampInt( 0, 6, state[1]->hPredictor );

			state[1]->coef1 = format.extra.adpcm.aCoef[state[1]->hPredictor].coef1;
			state[1]->coef2 = format.extra.adpcm.aCoef[state[1]->hPredictor].coef2;
		}

		state[0]->iDelta = ( ( encoded[1] << 8 ) | encoded[0] );
		encoded += sizeof( int16 );
		if( stereo )
		{
			state[1]->iDelta = ( ( encoded[1] << 8 ) | encoded[0] );
			encoded += sizeof( int16 );
		}

		state[0]->iSamp1 = ( ( encoded[1] << 8 ) | encoded[0] );
		encoded += sizeof( int16 );
		if( stereo )
		{
			state[1]->iSamp1 = ( ( encoded[1] << 8 ) | encoded[0] );
			encoded += sizeof( int16 );
		}

		state[0]->iSamp2 = ( ( encoded[1] << 8 ) | encoded[0] );
		encoded += sizeof( int16 );
		if( stereo )
		{
			state[1]->iSamp2 = ( ( encoded[1] << 8 ) | encoded[0] );
			encoded += sizeof( int16 );
		}



		// Store the two initial samples we start with
		decoded[0] = state[0]->iSamp2 & 0xFF;
		decoded[1] = ( state[0]->iSamp2 >> 8 ) & 0xFF;
		decoded += 2;
		if( stereo )
		{
			decoded[0] = state[1]->iSamp2 & 0xFF;
			decoded[1] = ( state[1]->iSamp2 >> 8 ) & 0xFF;
			decoded += 2;
		}

		decoded[0] = state[0]->iSamp1 & 0xFF;
		decoded[1] = ( state[0]->iSamp1 >> 8 ) & 0xFF;
		decoded += 2;
		if( stereo )
		{
			decoded[0] = state[1]->iSamp1 & 0xFF;
			decoded[1] = ( state[1]->iSamp1 >> 8 ) & 0xFF;
			decoded += 2;
		}

		// Decode and store the other samples in this block
		samplesleft = ( format.extra.adpcm.samplesPerBlock - 2 ) * format.basic.numChannels;

		while( samplesleft > 0 )
		{
			nybble = ( *encoded ) >> 4;
			new_sample = MS_ADPCM_nibble( state[0], nybble );

			decoded[0] = new_sample & 0xFF;
			decoded[1] = ( new_sample >> 8 ) & 0xFF;
			decoded += 2;

			nybble = ( *encoded ) & 0x0F;
			new_sample = MS_ADPCM_nibble( state[1], nybble );

			decoded[0] = new_sample & 0xFF;
			decoded[1] = ( new_sample >> 8 ) & 0xFF;
			decoded += 2;

			++encoded;
			samplesleft -= 2;
		}

		encoded_len -= format.basic.blockSize;
	}

	if( encoded_len != 0 || static_cast<size_t>( decoded - decodedBuffer ) != decodedBytes )
	{
		Mem_Free( decodedBuffer );
		return -1;
	}

	Mem_Free( originalBuffer );
	*audio_buf = decodedBuffer;
	*audio_len = static_cast<uint32_t>( decodedBytes );

	return 0;
}

