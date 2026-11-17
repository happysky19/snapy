#pragma once
// V3 lane R skeleton: declarations only, in no build. Rev 4, FROZEN with
// R.rst rev 2. Pin chengcli/snapy 9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410;
// bare :N is hydro_forward.cpp:N there. The contract is R.rst section 4.
// Units: flux density per unit face area and time at X's step dt, before
// stage weights. Frame: coord's flux2global<d>_ output. Dims 1..3 = x1..x3.
// Step: begin_step < post_split (meshblock.cpp:715) < stages < after_combine.
#include <cstdint>
#include <string>
#include <vector>
#include <torch/torch.h>

namespace harp { struct IntegratorWeight; }  // pyharp integrator.hpp:20-29
namespace snap {
class CoordinateImpl; class PrecisionPolicy; class RegisterMonitor;
enum class RegisterPhase : uint8_t {
  sweep,          // C's riemann + part slots; sedimentation; R's covariance
  reconcile,      // replace() on shared faces, then apply_prescribed(d)
  limit,          // EF: total read, theta sync (an exchange), carry, scale
  divergence,     // du reads total(d); later posts never enter du via R
  pre_implicit,   // A's sources; gravity work reads the limited x1 total
  implicit,       // I: add() posts, then keep(), then cell_amount()
  post_implicit,  // apply_prescribed(1); A's m1; I's G remainder, tracers
  after_combine,  // after X's RK combine: fixers, EF floors, K's chemistry
};
enum class SeamRule : uint8_t { mean, owner_copy };  // S rows 9 and 16r
//! O's R-O3: how the budget treats an amount
enum class AmountKind : uint8_t {
  flux_correction,  // a face change, already inside boundary(d): report only
  cell_source,      // volume source (A, K, vic.cell): the budget adds it
  floor,            // local floor or repair (EF, C): the budget adds it
  fixer,            // global Fixer (A's closure): the budget adds it
};
struct RegisterRequest {
  std::vector<std::string> row_names;  // nvar conserved rows, in row order
  std::vector<std::string> derived;    // hydro only: "e+pe" (I), "aam" (A)
  std::vector<std::string> keep;       // e.g. "riemann.central@2"
  std::vector<std::string> counters;   // C's five, EF's names (R.rst 4.2)
  std::vector<std::string> retry;      // causes, e.g. "implicit.column"
  std::vector<int> step_field;         // dims whose step field is read
};

class FluxRegister {  // one for hydro, one per Scalar module (R owns class)
 public:
  void reset(CoordinateImpl const* coord, PrecisionPolicy const& policy,
             int nvar, RegisterRequest const& req);
  //! S: mask bool [nvar, faces...] (row dimension), value [nvar, faces...]
  void set_prescribed(int dim, torch::Tensor const& mask,
                      torch::Tensor const& value);
  void begin_step();  // X, step start: zero step sums, monitor, counters
  void begin_stage(int stage, harp::IntegratorWeight const& w);  // X only
  void enter(RegisterPhase phase);
  //! in-place slots: the total (first post) or a requested part
  torch::Tensor slot(int dim, std::string const& name);
  torch::Tensor part_slot(int dim, std::string const& part);
  void post_slot(int dim, std::string const& name);
  //! in call order; a requested part of the same name is copied in the call
  void add(int dim, std::string const& name, std::vector<int> const& rows,
           torch::Tensor const& increment);
  //! total[rows] *= factor; factor [faces...] or [rows, faces...]
  void scale(int dim, std::string const& name, std::vector<int> const& rows,
             torch::Tensor const& factor);
  //! peer is already in this face's dim, basis and outward sign (S)
  void replace(int dim, torch::Tensor const& faces, torch::Tensor const& peer,
               SeamRule rule);
  void apply_prescribed(int dim);  // books "boundary.prescribed"
  void keep(int dim, std::string const& part, torch::Tensor const& value);
  //! V du per row (cell_volume interior). stage_weight: w2_s for an amount
  //! of this stage's du, 1.0 for a change already applied to u
  void cell_amount(std::string const& name, torch::Tensor const& vol_du,
                   double stage_weight, AmountKind kind);
  //! amount and step-end total on a derived row ("e+pe", "aam")
  void derived_amount(std::string const& name, std::string const& row,
                      torch::Tensor const& value, double stage_weight,
                      AmountKind kind);
  void derived_total(std::string const& row, torch::Tensor const& value);
  void count(std::string const& name, torch::Tensor const& n);  // += n
  void record_min(std::string const& name, torch::Tensor const& v);
  void flag_retry(std::string const& cause, torch::Tensor const& any);
  //! outside stages, weight as given, never scaled by later w1
  void post_split(int dim, std::string const& name, torch::Tensor const& flux,
                  double weight, double dt);
  torch::Tensor total(int dim) const;                         // kFlux view
  torch::Tensor kept(int dim, std::string const& part) const;  // view
  torch::Tensor step_field(int dim) const;  // kRegister, per unit area
  void end_stage(double dt);  // S = w1 S + w2 dt T; amounts likewise
  void rollback();            // register and monitor, on every block
  RegisterMonitor& monitor();
};
//! one per register instance; O reads after accept, never posts
class RegisterMonitor {
 public:
  void rollback();
  std::vector<std::string> row_names() const;  // conserved, then derived
  std::vector<std::string> amount_names() const;
  AmountKind kind(std::string const& name) const;
  torch::Tensor amounts(std::string const& name) const;  // (nrows,) FP64
  torch::Tensor boundary(int dim) const;  // area-integrated, outward, FP64
  torch::Tensor domain_total() const;     // fluid cells, (nrows,) FP64
  std::vector<std::string> counter_names() const;
  torch::Tensor counters() const;     // int64, counter_names() order
  torch::Tensor minima() const;       // FP64, record_min names in order
  torch::Tensor retry_flags() const;  // int32 0/1 per cause, X's one read
};
//! fixer base (A: AxialClosureFixer : Fixer); registry and collective: X
class Fixer {
 public:
  virtual ~Fixer() = default;
  virtual std::string name() const = 0;
  virtual std::vector<int> rows() const = 0;
  virtual torch::Tensor partial_sums() const = 0;  // FP64, to collective
  //! stage_weight: w2 of the stage just combined; posts cell_amount(...,
  //! 1.0, AmountKind::fixer) for the change it applies
  virtual void apply(torch::Tensor u, torch::Tensor const& global_sums,
                     double dt, double stage_weight,
                     FluxRegister& reg) const = 0;
};
}  // namespace snap
