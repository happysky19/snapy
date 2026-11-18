#pragma once
// V3 lane R skeleton: declarations only, in no build. Rev 4.3, with R.rst
// rev 2.3 (section 3). Pin chengcli/snapy 9e5de2d4. What HydroImpl::forward
// (hydro_forward.cpp:370-1696) becomes: one stage driver that calls the
// lanes' ops in RegisterPhase order and owns no flux, no fixer and no
// AAM state. Lines the driver no longer holds are counted in R.rst s9.
#include <memory>
#include <vector>
#include <torch/torch.h>

#include "flux_register.hpp"

namespace snap {
struct FaceDir;           // lane C sweep.hpp: reconstruct_faces and
struct FaceStates;        // solve_faces are C's free functions (no class)
class PositivityLimiter;   // lane EF
class SedimentationPost;   // lane EF: add(1, "sedimentation", ...)
class GravityWork;         // lane I: G[M] reads the register's x1 mass
class VerticalImplicit;    // lane I: posts vic.*
class SourceRegistry;      // lane A: SourcePhase pre/post_implicit, split
class SeamExchange;        // lane S: peer entries (rows 9, 16r), x1 relay
class SolidFaces;          // lane S: PrescribedFaces (mask with row dim)

//! what one stage reads that R does not own; all borrowed, never stored
struct StageInputs {
  torch::Tensor u, w;   // hydro_u (kHydroState), hydro_w (kPrimitive)
  torch::Tensor solid;  // immersed solid mask or undefined
  double dt;            // X's host dt (step dt, never dt_corr)
  int stage;
  harp::IntegratorWeight const* weight;  // this stage's, from X
};

//! the slimmed Hydro module: options parse, ownership and the stage driver
class HydroStage {
 public:
  //! the register request: rows from the EOS; A "riemann.central@2/3" in
  //! exact mode; I "vic.mass_total@1", "vic.mass_dry@1",
  //! "vic.momentum_t@1"; C "pressure_base1@1" on the split path (R-C3);
  //! O step_field {1}; counters and retry causes as in R.rst 4.2
  RegisterRequest request() const;

  //! sweep: x1, then x2/x3, by C's reconstruct_faces and solve_faces
  //! (slot, part slots); EF's sedimentation is an add()
  void sweep(StageInputs const& in, FluxRegister& reg);
  //! #289 covariance, RULING V3-3: build in C's before_solve (sweep.hpp:23)
  //! from post-solid, unrotated faces, no copy; post after the riemann slot
  void build_covariance(FaceStates const& faces, int dim);  // :1099-1100
  void post_covariance(int dim, FluxRegister& reg);  // add(d, "covariance")
  //! reconcile: replace() on every x1 seam (mean) and panel seam
  //! (owner_copy), after sedimentation, before positivity; apply_prescribed
  void reconcile(FluxRegister& reg);
  //! limit: EF reads total(d), theta sync, carry add()s in order, scale()
  void limit(StageInputs const& in, FluxRegister& reg);
  //! divergence: du = -div(total) through coord, then the p* sources
  torch::Tensor divergence(StageInputs const& in, FluxRegister const& reg);
  //! pre_implicit: A's sources; gravity work on the limited x1 total
  void pre_implicit(StageInputs const& in, torch::Tensor du, FluxRegister& reg);
  //! implicit: I's solve with dt_corr = w2_s dt for 3+ stages (:1568-1583);
  //! posts divide by A_f dt with the step dt
  void implicit(StageInputs const& in, torch::Tensor du, FluxRegister& reg);
  //! post_implicit: apply_prescribed(1); I's G remainder; A's m1 from A_f
  //! total(1) (today Phi, :1641, :1646); tracer transfer from vic.mass_dry
  void post_implicit(StageInputs const& in, torch::Tensor du,
                     FluxRegister& reg);
  //! the whole stage in that order, then reg.end_stage(dt); returns du
  torch::Tensor forward(StageInputs const& in, FluxRegister& reg);
  //! after_combine: no HydroStage op; X's StageExecutor::after_combine(stage,
  //! dt) is its one runner, after finish_step on the last stage. meshblock.cpp
  //! order: EF's F1 :907-909, X's scalars :920-923, S's solid :936-938; last
  //! stage with reactions F1b :952, K :954-972; then A's closure :983-990

 private:
  std::shared_ptr<PositivityLimiter> limiter_;
  std::shared_ptr<SedimentationPost> sed_;
  std::shared_ptr<GravityWork> gravity_;
  std::shared_ptr<VerticalImplicit> implicit_;
  std::shared_ptr<SourceRegistry> sources_;
  std::shared_ptr<SeamExchange> seams_;
  std::shared_ptr<SolidFaces> solids_;
};

}  // namespace snap
