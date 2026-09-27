# Quake 4: The Awakening (q4xbase) game modules.
#
# openQ4-game-awakening is a game-library layer (tools/build/game_layer.py).
# tools/build/stage_gamelibs.py --layer copies its sources into
# src/game/<id>/ and src/mpgame/<id>/ of a stage that also holds the
# unchanged openQ4-game trees, so layer sources include base headers exactly as
# base sources do. Only the layer's sources are compiled here; each module
# links the same openQ4-game core library as the baseoq4 module
# (content/baseoq4/meson.build), so q4xbase always runs the current openQ4 game
# plus the layer. See docs/dev/plans/q4x-awakening.md.

if awakening_game_dir != 'q4xbase'
  error('The openQ4-game-awakening layer must target q4xbase, not ' + awakening_game_dir + '.')
endif

awakening_install_dir = install_root_dir / awakening_game_dir
awakening_direct_run_dir = meson.project_build_root() / awakening_game_dir

awakening_manifest = custom_target(
  'openq4_awakening_mod_manifest',
  output: 'mod.json',
  command: [
    py,
    meson.project_source_root() / 'tools' / 'build' / 'game_layer.py',
    'mod-json',
    awakening_repo_root,
    '--openq4-version',
    openq4_version_base,
    '--out',
    '@OUTPUT@',
  ],
  depend_files: [files('../../tools/build/game_layer.py'), awakening_repo_root / 'layer.json'],
  build_by_default: true,
  install: true,
  install_dir: awakening_install_dir,
)

custom_target(
  'openq4_awakening_stage_mod_manifest_direct_run',
  input: awakening_manifest,
  output: 'stage-awakening-mod-manifest.stamp',
  command: [
    py,
    meson.project_source_root() / 'tools' / 'build' / 'stage_direct_run_game_module.py',
    '--source',
    '@INPUT@',
    '--destination',
    awakening_direct_run_dir / 'mod.json',
    '--stamp',
    '@OUTPUT@',
  ],
  depend_files: files('../../tools/build/stage_direct_run_game_module.py'),
  build_always_stale: true,
  build_by_default: true,
)

awakening_modules = []

if build_game_sp
  awakening_sp_discovery = run_command(
    py,
    meson.project_source_root() / 'tools' / 'build' / 'list_sources.py',
    awakening_stage_root,
    'src/game/' + awakening_layer_id,
    check: true,
  )
  awakening_sp_paths = []
  foreach rel_path : awakening_sp_discovery.stdout().strip().split('\n')
    if rel_path.strip() != ''
      awakening_sp_paths += [awakening_stage_root / rel_path.strip()]
    endif
  endforeach
  awakening_sp_sources = files(awakening_sp_paths) + [savegame_compat_header, generated_version_header]

  if host_system == 'windows'
    awakening_sp_module = shared_module(
      game_sp_binary_name,
      awakening_sp_sources,
      include_directories: awakening_game_include_dirs,
      link_whole: game_sp_core_library,
      link_with: game_idlib_library,
      cpp_args: game_common_cpp_args,
      c_args: game_common_c_args,
      cpp_pch: game_module_pch_headers,
      override_options: game_target_override_options,
      link_args: game_module_link_args,
      vs_module_defs: game_sp_module_defs_file,
      name_prefix: module_filename_prefix,
      install: true,
      install_dir: awakening_install_dir,
    )
  elif host_system == 'darwin'
    awakening_sp_module = shared_library(
      game_sp_binary_name,
      awakening_sp_sources,
      include_directories: awakening_game_include_dirs,
      link_whole: game_sp_core_library,
      link_with: game_idlib_library,
      cpp_args: game_common_cpp_args,
      c_args: game_common_c_args,
      cpp_pch: game_module_pch_headers,
      override_options: game_target_override_options,
      link_args: game_module_link_args + ['-Wl,-install_name,@loader_path/' + game_sp_binary_name + '.dylib'],
      link_depends: game_module_link_depends,
      gnu_symbol_visibility: 'hidden',
      name_prefix: module_filename_prefix,
      name_suffix: 'dylib',
      install: true,
      install_dir: awakening_install_dir,
    )
  else
    awakening_sp_module = shared_module(
      game_sp_binary_name,
      awakening_sp_sources,
      include_directories: awakening_game_include_dirs,
      link_whole: game_sp_core_library,
      link_with: game_idlib_library,
      cpp_args: game_common_cpp_args,
      c_args: game_common_c_args,
      cpp_pch: game_module_pch_headers,
      override_options: game_target_override_options,
      link_args: game_module_link_args,
      link_depends: game_module_link_depends,
      gnu_symbol_visibility: 'hidden',
      name_prefix: module_filename_prefix,
      install: true,
      install_dir: awakening_install_dir,
    )
  endif
  awakening_modules += [[awakening_sp_module, game_sp_binary_name, 'sp']]
endif

if build_game_mp
  awakening_mp_discovery = run_command(
    py,
    meson.project_source_root() / 'tools' / 'build' / 'list_sources.py',
    awakening_stage_root,
    'src/mpgame/' + awakening_layer_id,
    check: true,
  )
  awakening_mp_paths = []
  foreach rel_path : awakening_mp_discovery.stdout().strip().split('\n')
    if rel_path.strip() != ''
      awakening_mp_paths += [awakening_stage_root / rel_path.strip()]
    endif
  endforeach
  awakening_mp_sources = files(awakening_mp_paths) + [savegame_compat_header, generated_version_header]

  if host_system == 'windows'
    awakening_mp_module = shared_module(
      game_mp_binary_name,
      awakening_mp_sources,
      include_directories: awakening_game_include_dirs,
      link_whole: game_mp_core_library,
      link_with: game_idlib_library_mp,
      cpp_args: game_common_cpp_args + ['-DGAME_MPAPI'],
      c_args: game_common_c_args,
      cpp_pch: game_module_pch_headers,
      override_options: game_target_override_options,
      link_args: game_module_link_args,
      vs_module_defs: game_mp_module_defs_file,
      name_prefix: module_filename_prefix,
      install: true,
      install_dir: awakening_install_dir,
    )
  elif host_system == 'darwin'
    awakening_mp_module = shared_library(
      game_mp_binary_name,
      awakening_mp_sources,
      include_directories: awakening_game_include_dirs,
      link_whole: game_mp_core_library,
      link_with: game_idlib_library_mp,
      cpp_args: game_common_cpp_args + ['-DGAME_MPAPI'],
      c_args: game_common_c_args,
      cpp_pch: game_module_pch_headers,
      override_options: game_target_override_options,
      link_args: game_module_link_args + ['-Wl,-install_name,@loader_path/' + game_mp_binary_name + '.dylib'],
      link_depends: game_module_link_depends,
      gnu_symbol_visibility: 'hidden',
      name_prefix: module_filename_prefix,
      name_suffix: 'dylib',
      install: true,
      install_dir: awakening_install_dir,
    )
  else
    awakening_mp_module = shared_module(
      game_mp_binary_name,
      awakening_mp_sources,
      include_directories: awakening_game_include_dirs,
      link_whole: game_mp_core_library,
      link_with: game_idlib_library_mp,
      cpp_args: game_common_cpp_args + ['-DGAME_MPAPI'],
      c_args: game_common_c_args,
      cpp_pch: game_module_pch_headers,
      override_options: game_target_override_options,
      link_args: game_module_link_args,
      link_depends: game_module_link_depends,
      gnu_symbol_visibility: 'hidden',
      name_prefix: module_filename_prefix,
      install: true,
      install_dir: awakening_install_dir,
    )
  endif
  awakening_modules += [[awakening_mp_module, game_mp_binary_name, 'mp']]
endif

foreach module_info : awakening_modules
  custom_target(
    'openq4_awakening_stage_game_' + module_info[2] + '_direct_run',
    input: module_info[0],
    output: 'stage-awakening-game-' + module_info[2] + '-' + binary_arch + '.stamp',
    command: [
      py,
      meson.project_source_root() / 'tools' / 'build' / 'stage_direct_run_game_module.py',
      '--source',
      '@INPUT@',
      '--destination',
      awakening_direct_run_dir / (module_filename_prefix + module_info[1] + game_module_filename_suffix),
      '--stamp',
      '@OUTPUT@',
    ],
    depend_files: files('../../tools/build/stage_direct_run_game_module.py'),
    build_always_stale: true,
    build_by_default: true,
  )
endforeach
