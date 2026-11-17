#pragma once
// V3 lane R skeleton: declarations only, in no build. PROVISIONAL, rev 1.
// Pin chengcli/snapy 9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410; lines are at
// the pin (hydro_forward.cpp unless named). Untested claims: "hypothesis".
// 1 UNITS. A post is a flux density per unit face area and time at the step
//   dt, before stage weights, in global components after coord's rotation.
//   Face i lies between cells i-1, i. The divergence applies face_area<d>
//   (coordinate.cpp:706). vic.* posts M/(A dt), as :1641,1646 do today.
// 2 PARTS. Posts are named. A part is a field only if requested (keep):
//   riemann.central = ONE summed mass row, dry + species, from the solver's
//   own face states, totals under perturbation flux, valid to the next
//   begin_stage. Other parts: FP64 monitor amounts only, no per-face read.
// 3 WEIGHTS. Stage total in Quantity::kFlux. end_stage adds c_s*dt*total to
//   an FP64 step accumulator (kRegister FP64 in both precisions), with
//   c_s = w2_s * prod_{t>s} w1_t in host double (:1682-1691).
// 4 CORRECTIONS. add() is in place, in post order (carry). scale()
//   multiplies the running total, bitwise F*=theta
//   (flux_positivity.cpp:99-121). replace() applies the seam rule. Kept parts
//   are reconciled, never scaled (cen2 :1356 and bflux1 :847 are unscaled).
// 5 READS. total(d) at the caller's phase; kept(); boundary sums. No EOS call.
// 6 MONITOR. R owns it: per-post FP64 amounts, counters and domain totals,
//   stacked into X's one step-end read (meshblock.cpp:1566).
// 7 RESET. begin_stage(0) zeroes the step, rollback() all (X's reset list,
//   meshblock.cpp:735). Nothing to restart. EF's 108 lines are R deletions.
// Order: x1 riemann :845 < sedimentation :861-866 < x1 seam replace :882 <
//   x2/x3 riemann, covariance :1050-1152 < positivity :1154-1252 <
//   divergence :1254 < forcings, gravity work :1412 < implicit :1554-1616 <
//   post_implicit :1618-1680 < end_stage.
// CONFLICTS/OPEN: C posts positivity as (theta-1)F, R scales. X keeps face
//   data only, so vic.cell is a monitor amount. X's begin_stage weight lacks
//   w1_t, t>s. Namespace snap vs snap::v3. vic.mass_clamped is a floor
//   amount, not a post. vic energy as face transfer only if the wall
//   residual is round-off (hypothesis). Gravity-work deletion: 133 vs 112.
#include <cstdint>
#include <string>
#include <vector>
#include <torch/torch.h>

namespace snap {  // X and C use snap; A and EF drafts use snap::v3
class CoordinateImpl;
class PrecisionPolicy;  // lane X
//! posts allowed per phase (checked in debug builds only)
enum class RegisterPhase : uint8_t {
  sweep,          // riemann (+ kept parts), sedimentation, covariance
  reconcile,      // seam replace; an exchange phase of X/S
  limit,          // positivity: scale (withhold), add (carry)
  divergence,     // du reads total(d); later posts never enter du via R
  pre_implicit,   // forcings; gravity work reads the explicit x1 total
  implicit,       // vic.mass_dry/species/momentum_t posts; vic.mass_total kept
  post_implicit,  // A's m1 rows, gravity-work remainder, tracer transfer
};

//! pyharp IntegratorWeight of every stage, host doubles
struct StageWeights { std::vector<double> w0, w1, w2; };

//! keep: "riemann.central@2", "vic.mass_total@1"; step_field: FP64 dims read
struct RegisterRequest {
  std::vector<std::string> keep;
  std::vector<int> step_field;
};

class FluxRegister {
 public:
  //! fixed storage from X's StateStore; nvar rows per active dim
  void reset(CoordinateImpl const* coord, PrecisionPolicy const& policy,
             int nvar, StageWeights const& weights, RegisterRequest const& req);
  //! X's call; the table gives w1_t for t > s; a graph bakes c_s in
  void begin_stage(int stage, StageWeights const& weights);
  void enter(RegisterPhase phase);

  //! first post of a stage: the solver writes the total in place
  torch::Tensor slot(int dim, std::string const& name);
  void post_slot(int dim, std::string const& name);
  void add(int dim, std::string const& name, std::vector<int> const& rows,
           torch::Tensor const& increment);
  //! total[rows] *= factor; the amount (factor-1)*F goes to the monitor
  void scale(int dim, std::string const& name, std::vector<int> const& rows,
             torch::Tensor const& factor);
  //! seam values on total and kept parts; R owns the rule, S the transport
  void replace(int dim, std::string const& name, torch::Tensor const& seam);
  //! a requested part, or a companion such as riemann.pstar (kGauge)
  void keep(int dim, std::string const& part, torch::Tensor const& value);
  //! cell increment (vic.cell, fixers, floors): monitor amount, no field
  void cell_amount(std::string const& name, torch::Tensor const& vol_du);
  //! split op outside stages; radial conduction 0.5 a half (meshblock:715,905)
  void post_split(int dim, std::string const& name, torch::Tensor const& flux,
                  double weight, double dt);

  torch::Tensor total(int dim) const;                         // kFlux view
  torch::Tensor kept(int dim, std::string const& part) const;  // view
  torch::Tensor step_field(int dim) const;  // FP64 sum c_s dt F, per area
  void end_stage(double dt);                // FP64 step and boundary sums
  void rollback();
};

//! one device monitor per block; O reads it after accept and never posts
class RegisterMonitor {
 public:
  torch::Tensor amounts(std::string const& name) const;  // (nrows,) FP64
  torch::Tensor boundary(int dim) const;  // outward step transfer, FP64
  torch::Tensor domain_total() const;     // per row, step-end state, FP64
  torch::Tensor counters() const;         // floors, p* clamps, events
  torch::Tensor retry_flags() const;      // joins X's stacked read
};

//! fixer/floor base (A: AxialClosureFixer : Fixer); registry is X's (X-2)
class Fixer {
 public:
  virtual ~Fixer() = default;
  virtual std::string name() const = 0;
  virtual std::vector<int> rows() const = 0;
  virtual torch::Tensor partial_sums() const = 0;  // FP64, to collective
  virtual void apply(torch::Tensor u, torch::Tensor const& global_sums,
                     double dt, double stage_weight,
                     FluxRegister& reg) const = 0;  // posts cell_amount
};

}  // namespace snap
