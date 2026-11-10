// C/C++
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>

// kintera
#include <kintera/utils/serialize.hpp>

// snap
#include <snap/mesh/meshblock.hpp>

#include "output_formats.hpp"
#include "output_utils.hpp"

namespace snap {

RestartOutput::RestartOutput(OutputOptions const& options_)
    : OutputType(options_) {
  // restart files are always combined
  options->combine(true);
}

void RestartOutput::write_output_file(MeshBlockImpl* pmb, Variables const& vars,
                                      double current_time, bool final_write) {
  // make a cpu copy of variables
  Variables out_vars;
  bool skip_scalar_r = vars.count("scalar_s") && vars.count("hydro_u");
  for (auto const& [name, var] : vars) {
    if (skip_scalar_r && name == "scalar_r") {
      continue;
    }
    if (var.defined()) {
      out_vars[name] = var.to(torch::kCPU);
    }
  }

  // store last time and cycle
  out_vars["last_time"] = torch::tensor({current_time}, torch::kFloat64);
  out_vars["last_cycle"] = torch::tensor({(int64_t)pmb->cycle}, torch::kInt64);
  // H_ref of the factored x1 reference rows: set once at setup from the bottom
  // cells, so a restart must not recompute it from the cells it finds then
  if (pmb->phydro && pmb->phydro->x1_href() > 0.) {
    out_vars["x1_href"] =
        torch::tensor({pmb->phydro->x1_href()}, torch::kFloat64);
  }

  // save file number and next time for each output type
  std::vector<int> output_file_numbers;
  std::vector<double> output_next_times;
  std::vector<int64_t> output_keys;

  // make_outputs advances an output's schedule only after writing it. Save the
  // advanced schedule for this restart and the outputs after it that fire in
  // the same pass, so a resume does not write their t0 files again.
  bool firing = false;
  for (auto out : pmb->output_types) {
    if (out.get() == this) firing = !final_write;
    bool advance = firing && current_time >= out->next_time;
    output_file_numbers.push_back(out->file_number + (advance ? 1 : 0));
    output_next_times.push_back(out->next_time +
                                (advance ? out->options->dt() : 0.0));
    output_keys.push_back(out->schedule_key());
  }
  // Old readers use the first N entries. Precise keys follow them in the same
  // tensor, so an old writer naturally replaces the whole value with N legacy
  // entries instead of carrying unknown metadata into a later new restart.
  for (auto out : pmb->output_types) {
    output_keys.push_back(out->schedule_key_v2());
  }

  out_vars["file_number"] = torch::tensor(output_file_numbers, torch::kInt64);
  out_vars["next_time"] = torch::tensor(output_next_times, torch::kFloat64);
  out_vars["output_key"] = torch::tensor(output_keys, torch::kInt64);

  // create filename: <basename>.<blockid>.<file_number>.part
  std::string fname;
  char number[6];
  snprintf(number, sizeof(number), "%05d", file_number);
  char blockid[12];
  snprintf(blockid, sizeof(blockid), "block%d", pmb->options->layout()->rank());

  fname.assign(pmb->options->output_dir());
  fname.append("/");
  fname.append(pmb->options->basename());
  fname.append(".");
  fname.append(blockid);
  fname.append(".");
  if (final_write) {
    fname.append("final");
  } else {
    fname.append(number);
  }
  fname.append(".part");

  // save to disk
  std::error_code ec;
  std::filesystem::create_directories(pmb->options->output_dir(), ec);
  if (ec) {
    throw std::runtime_error("Failed to create output directory '" +
                             pmb->options->output_dir() + "': " + ec.message());
  }
  kintera::save_tensors(out_vars, fname);

  if (options->combine()) {
    combine_blocks(pmb, final_write);
  }
}

}  // namespace snap
