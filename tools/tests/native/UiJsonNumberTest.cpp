// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
// JsonCpp number decoding with openQ4's subnormal-numbers.patch. Both readers
// decode through `istringstream >> double`, so they are run against the
// platform's num_get and against the num_get contract of libc++ over a gdtoa
// strtod (Apple, FreeBSD, Android). There strtod reports ERANGE for every
// subnormal or underflowing result, and libc++ sets failbit but still stores
// the value. The MSVC STL and libstdc++ never fail there, so only the emulated
// facet reaches the patched branch on Windows and Linux.
#include <json/json.h>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <locale>
#include <memory>
#include <string>
#if defined(__SSE__) || defined(_M_X64)
#include <xmmintrin.h>
#define TEST_SSE 1
#endif
// Json::Reader is deprecated upstream, but the patch changes it too.
#if defined(_MSC_VER)
#pragma warning(disable: 4996)
#elif defined(__GNUC__)
#pragma GCC diagnostic ignored "-Wdeprecated-declarations"
#endif
static unsigned checks;
#define CHECK(x) do{++checks;if(!(x)){std::fprintf(stderr,"FAIL %d (check %u): %s\n",__LINE__,checks,#x);std::exit(1);}}while(false)

static std::uint64_t Bits(double value) { std::uint64_t bits; std::memcpy(&bits,&value,sizeof(bits)); return bits; }

// Denormals-are-zero only, where the target exposes it: floating comparisons
// then see a subnormal as zero, so the patch must classify it from its bits.
// Not flush-to-zero, because gdtoa computes a subnormal result with a final
// floating multiply that FTZ would flush before any decoder could see it.
struct DenormalsAreZero {
#if TEST_SSE
	unsigned old=_mm_getcsr();DenormalsAreZero(){_mm_setcsr(old|0x40u);}~DenormalsAreZero(){_mm_setcsr(old);}
#else
	DenormalsAreZero(){}
#endif
};

// libc++'s __num_get_float fed by a gdtoa strtod. Stage 2 gathers the field;
// a partial conversion fails with 0, and a range error fails but keeps the
// value, which is subnormal, zero after underflow or infinite after overflow.
class LibcxxGdtoaNumGet final : public std::num_get<char> {
protected:
	using std::num_get<char>::do_get;
	iter_type do_get(iter_type in, iter_type end, std::ios_base&, std::ios_base::iostate& state, double& value) const override {
		std::string field;
		for (; in != end && *in != '\0' && std::strchr("0123456789+-.eE",*in); ++in) field += *in;
		if (in == end) state |= std::ios_base::eofbit;
		char* stop = nullptr;
		errno = 0;
		const double parsed = std::strtod(field.c_str(),&stop);
		const bool range = errno == ERANGE;
		if (field.empty() || stop != field.c_str() + field.size()) { state |= std::ios_base::failbit; value = 0; return in; }
		const bool nonzeroDigits = field.find_first_of("123456789") < field.find_first_of("eE");
		const bool tiny = (Bits(parsed) & 0x7fffffffffffffffULL) < 0x0010000000000000ULL && nonzeroDigits;
		if (range || tiny) state |= std::ios_base::failbit;
		value = parsed;
		return in;
	}
};

static bool Parse(const std::string& text, bool legacy, Json::Value& root, std::string& errors) {
	if (legacy) {
		Json::Reader reader;
		const bool ok = reader.parse(text,root,false);
		errors = reader.getFormattedErrorMessages();
		return ok;
	}
	Json::CharReaderBuilder builder;
	std::unique_ptr<Json::CharReader> reader(builder.newCharReader());
	return reader->parse(text.data(),text.data() + text.size(),&root,&errors);
}
static void Decodes(const std::string& token, std::uint64_t bits) {
	for (bool legacy : {false,true}) {
		Json::Value root; std::string errors;
		CHECK(Parse("[" + token + "]",legacy,root,errors));
		CHECK(root.isArray() && root.size() == 1 && root[0u].isDouble());
		CHECK(Bits(root[0u].asDouble()) == bits);
	}
}
static void Rejects(const std::string& token) {
	for (bool legacy : {false,true}) {
		Json::Value root; std::string errors;
		CHECK(!Parse("[" + token + "]",legacy,root,errors));
		CHECK(errors.find("'" + token + "' is not a number") != std::string::npos);
	}
}

// Every library must decode these exactly, subnormal or not.
static void Numbers() {
	Decodes("4.9406564584124654e-324",0x0000000000000001ULL);
	Decodes("-4.9406564584124654e-324",0x8000000000000001ULL);
	Decodes("9.8813129168249309e-324",0x0000000000000002ULL);
	Decodes("3e-324",0x0000000000000001ULL);
	Decodes("2.2250738585072009e-308",0x000fffffffffffffULL);
	Decodes("0." + std::string(323,'0') + "49406564584124654",0x0000000000000001ULL);
	Decodes("2.2250738585072014e-308",0x0010000000000000ULL);
	Decodes("1.5",0x3ff8000000000000ULL);
}

int main() {
	Numbers();
	{ DenormalsAreZero daz; Numbers(); }
	const std::locale original = std::locale::global(std::locale(std::locale::classic(),new LibcxxGdtoaNumGet));
	Numbers();
	{ DenormalsAreZero daz; Numbers(); }
	// Underflow to zero stays an error, and overflow still decodes as infinity.
	Rejects("1e-400");
	Rejects("-1e-400");
	Rejects("2e-324");
	Decodes("1e309",0x7ff0000000000000ULL);
	Decodes("-1e309",0xfff0000000000000ULL);
	std::locale::global(original);
	std::printf("UiJsonNumberTest: %u checks passed\n",checks);
}
