#pragma once
// V3 lane R skeleton: declarations only, in no build. PROVISIONAL, rev 2
// (R.rst rev 1.1). Pin chengcli/snapy 9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410;
// lines are hydro_forward.cpp at the pin unless named. Untested: hypothesis.
// 1 UNITS. Posts are flux densities per unit face area and time at X's step
//   dt, before stage weights. The pin forms area-integrated rates instead,
//   Phi = A F1 + M/dt (:1641, :1646). vic.* posts M/(A_f dt), not dt_corr.
// 2 FRAME. The output of coord's flux2global<d>_ (coordinate.hpp:353-361).
// 3 PARTS. Fields only on request, else FP64 monitor amounts.
//   riemann.central@2/@3: ONE summed x2/x3 mass row, dry + species, from the
//   states after pib->forward (:1089-1090, :1123-1124; cen2 :1108), totals.
//   No x1 Riemann-only row: bflux1 (:846-849) was the removed cell form.
// 4 WEIGHTS. X owns them (begin_stage). end_stage runs S = w1_s S + w2_s dt T:
//   coefficients w2_s prod_{t>s} w1_t (:1685-1691). FP64; FP32 on MPS
//   (meshblock.cpp:1057).
// 5 CORRECTIONS. add() in place, in call order, never pre-summed (carry:
//   x1 advected, then settling, before scale). scale() is bitwise F*=theta
//   (flux_positivity.cpp:99-121, :154-159). replace(): own and peer entry,
//   one rule. Kept parts are never scaled (_flux2 - cen2 at :1358-1359).
// 6 MONITOR. Amounts, counters, fluid-cell domain totals, retry flags; read
//   once at step end (meshblock.cpp:1566).
// 7 BOUNDARY. "boundary.prescribed": S's wall/solid mask and values, applied
//   after reconcile and after post_implicit, booked as a correction.
#include <cstdint>
#include <string>
#include <vector>
#include <torch/torch.h>

namespace harp { struct IntegratorWeight; }  // pyharp integrator.hpp:20-29

namespace snap {  // A rev 2, C rev 5, EF and X use snap
class CoordinateImpl; class PrecisionPolicy; class RegisterMonitor;
//! posts allowed per phase (checked in debug builds only)
enum class RegisterPhase : uint8_t {
  sweep,          // riemann and part slots, sedimentation, covariance
  reconcile,      // replace() on shared faces, then boundary.prescribed
  limit,          // positivity: carry adds in order, then scale
  divergence,     // du reads total(d); later posts never enter du via R
  pre_implicit,   // A's sources; gravity work reads the limited x1 total
  implicit,       // vic.mass_dry/species/momentum_t adds; vic.mass_* kept
  post_implicit,  // boundary.prescribed again; A's m1, I's G remainder
  after_combine,  // fixers after the RK combine (meshblock.cpp:907-909)
};
//! one rule per shared face; S moves the peer entry (S.rst row 9)
enum class SeamRule : uint8_t { mean };
//! keep: "riemann.central@2", "vic.mass_total@1", "vic.mass_dry@1";
//! dims 1 = x1, 2 = x2, 3 = x3; counters: names (EF's 12 among them)
struct RegisterRequest {
  std::vector<std::string> keep, counters;
  std::vector<int> step_field;  // dims whose step field a reader needs
};

class FluxRegister {
 public:
  //! fixed storage (X's StateStore); one instance for hydro, one per Scalar
  //! module; R owns the class, not the instances
  void reset(CoordinateImpl const* coord, PrecisionPolicy const& policy,
             int nvar, RegisterRequest const& req);
  //! lane S's wall and immersed-solid faces: mask and prescribed rows
  void set_prescribed(int dim, torch::Tensor const& mask,
                      torch::Tensor const& value);
  //! X's call (X.rst s4), the only owner of the stage weights
  void begin_stage(int stage, harp::IntegratorWeight const& w);
  void enter(RegisterPhase phase);
  //! in-place slots: the total for the first post, or a requested part
  torch::Tensor slot(int dim, std::string const& name);
  torch::Tensor part_slot(int dim, std::string const& part);
  void post_slot(int dim, std::string const& name);
  void add(int dim, std::string const& name, std::vector<int> const& rows,
           torch::Tensor const& increment);
  //! total[rows] *= factor; the amount (factor-1)*F goes to the monitor
  void scale(int dim, std::string const& name, std::vector<int> const& rows,
             torch::Tensor const& factor);
  //! own vs peer entry on shared faces, then the rule: total, kept parts,
  //! companions (riemann.pstar, pressure_base1)
  void replace(int dim, torch::Tensor const& faces, torch::Tensor const& peer,
               SeamRule rule);
  void apply_prescribed(int dim);  // books "boundary.prescribed"
  //! a computed one-row part (one row copied)
  void keep(int dim, std::string const& part, torch::Tensor const& value);
  //! cell increment (vic.cell, fixers, floors): monitor amount, no field
  void cell_amount(std::string const& name, torch::Tensor const& vol_du);
  //! named counter += n on device (face floors, p* clamps, EF status)
  void count(std::string const& name, torch::Tensor const& n);
  //! split op outside stages; radial conduction 0.5 a half (meshblock:715,905)
  void post_split(int dim, std::string const& name, torch::Tensor const& flux,
                  double weight, double dt);
  torch::Tensor total(int dim) const;                         // kFlux view
  torch::Tensor kept(int dim, std::string const& part) const;  // view
  torch::Tensor step_field(int dim) const;  // kRegister, per unit area
  void end_stage(double dt);                // step and boundary recursion
  void rollback();                          // also rolls the monitor back
  RegisterMonitor& monitor();
};
//! one device monitor per register; O reads it after accept, never posts
class RegisterMonitor {
 public:
  void reset_step();  // at begin_stage(0)
  void rollback();    // X's decide_retry, on every block
  torch::Tensor amounts(std::string const& name) const;  // (nrows,) FP64
  torch::Tensor boundary(int dim) const;  // outward step transfer, FP64
  torch::Tensor domain_total() const;     // fluid cells only, FP64
  torch::Tensor counter(std::string const& name) const;
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
