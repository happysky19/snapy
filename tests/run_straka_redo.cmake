# run_straka_redo.cmake: straka on one process at cfl 1.6 (shipped 0.9) to
# t = 40 s. Steps there go non-finite and are redone with a smaller dt; with
# gravity-work: cell and its default fixer on, they must reach the redo check and the
# run its time limit. (Longer runs at this cfl end by chance on the redo limit,
# with or without the fixer.)
#
# 40 s rather than 60 is margin, not a reproduction of a local failure. The
# unperturbed run reaches tlim with exit 0 at 40, 60 AND 80 s on this branch
# (measured here: 156, 224 and 304 redos), so nothing fails at 60 s. The margin
# is taken against a perturbed-seed sweep reported on the two EARLIER row
# schemes of this PR -- 25 runs per build with a 1e-12 relative theta
# perturbation, earliest redo-limit stop 42.03 s with the p rows and 51.59 s
# with the ln p candidate. That sweep needs a seed hook this tree does not have
# and has NOT been re-run against the factored rows, so 40 s is carried over as
# the conservative bound, not measured for this kernel.

get_filename_component(build_dir "${CMAKE_CURRENT_BINARY_DIR}/.." ABSOLUTE)
set(work_dir "${CMAKE_CURRENT_BINARY_DIR}/straka_redo")
file(REMOVE_RECURSE "${work_dir}")
file(MAKE_DIRECTORY "${work_dir}")

file(READ "${build_dir}/bin/straka_single.yaml" config)
string(REPLACE "cfl: 0.9" "cfl: 1.6" config "${config}")
string(REPLACE "tlim: 900" "tlim: 40" config "${config}")
string(REPLACE "grav1: -9.8\n" "grav1: -9.8\n    gravity-work: cell\n" config "${config}")
if(NOT config MATCHES "cfl: 1.6" OR NOT config MATCHES "tlim: 40"
   OR NOT config MATCHES "gravity-work: cell")
  message(FATAL_ERROR "straka_single.yaml: no 'cfl: 0.9' / 'tlim: 900' / 'grav1: -9.8' to set")
endif()
file(WRITE "${work_dir}/straka.yaml" "${config}")

execute_process(
  COMMAND "${build_dir}/bin/straka.${buildl}" straka.yaml
  WORKING_DIRECTORY "${work_dir}"
  RESULT_VARIABLE res
  OUTPUT_VARIABLE out
  ERROR_VARIABLE out
)

if(NOT res EQUAL 0)
  message(FATAL_ERROR "straka at cfl 1.6 stopped with exit code ${res}:\n${out}")
endif()
if(NOT out MATCHES "Redoing the step")
  message(FATAL_ERROR "straka at cfl 1.6 redid no step: the case no longer tests the redo path")
endif()
