#pragma once
// V3 lane R skeleton: declarations only, in no build. PROVISIONAL (R.rst
// rev 1, section 3). Pin chengcli/snapy 9e5de2d4. What HydroImpl::forward
// (hydro_forward.cpp:370-1696) becomes: one stage driver that calls the
// lanes' ops in RegisterPhase order and owns no flux, no fixer and no
// AAM state. Lines the driver no longer holds are counted in R.rst s9.
#include <memory>
#include <vector>
#include <torch/torch.h>

#include "flux_register.hpp"

namespace snap {
class RiemannSolverImpl;   // lane C (riemann.hpp)
class Sweep;               // lane C (sweep.hpp): recon + solve_faces
class PositivityLimiter;   // lane EF
class SedimentationPost;   // lane EF: posts "sedimentation" on x1
class GravityWork;         // lane I: G[M] reads the register's x1 mass
class VerticalImplicit;    // lane I: posts vic.*
class SourceRegistry;      // lane A: SourcePhase pre/post_implicit, split
class SeamExchange;        // lane S: transport of the two-sided seam entry

//! what one stage reads that R does not own; all borrowed, never stored
struct StageInputs {
  torch::Tensor u, w;        // hydro_u (kHydroState), hydro_w (kPrimitive)
  torch::Tensor solid;       // immersed solid mask or undefined
  double dt;                 // X's host dt (step dt, not stage-weighted)
  int stage;
};

//! the slimmed Hydro module: options parse, ownership and the stage driver
class HydroStage {
 public:
  //! builds the register request from the lanes' needs: A asks
  //! "riemann.central@2/3" when its exact mode is on; I asks
  //! "vic.mass_total@1"; O asks step_field {1} for its x1 profile
  RegisterRequest request() const;

  //! sweep phase: x1, then x2/x3 (C posts riemann via slot/post_slot,
  //! C's covariance via add; EF's sedimentation via add on x1 rows)
  void sweep(StageInputs const& in, FluxRegister& reg);
  //! reconcile phase: x1 seam replace (:868-946 today), after sedimentation
  //! and before positivity; S moves the two entries, R applies the rule
  void reconcile(FluxRegister& reg);
  //! limit phase: EF reads total(d) once, then scale (species) and add
  //! (carry: IPR, IVX..IVZ, x1 advected before settling part)
  void limit(StageInputs const& in, FluxRegister& reg);
  //! divergence phase: du = -div(total) through coord, p* sources
  torch::Tensor divergence(StageInputs const& in, FluxRegister const& reg);
  //! pre_implicit: A's sources, gravity work on the explicit x1 total
  void pre_implicit(StageInputs const& in, torch::Tensor du, FluxRegister& reg);
  //! implicit: I's solve with dt_corr = w2_s dt for 3+ stages (:1568-1583)
  void implicit(StageInputs const& in, torch::Tensor du, FluxRegister& reg);
  //! post_implicit: A's m1 rows and axial x1 source, I's G remainder and
  //! tracer donor transfer; all read total(1) and kept("vic.mass_total")
  void post_implicit(StageInputs const& in, torch::Tensor du,
                     FluxRegister& reg);

  //! the whole stage in that order, then reg.end_stage(dt); returns du
  torch::Tensor forward(StageInputs const& in, FluxRegister& reg);

 private:
  std::shared_ptr<Sweep> sweep_;
  std::shared_ptr<PositivityLimiter> limiter_;
  std::shared_ptr<SedimentationPost> sed_;
  std::shared_ptr<GravityWork> gravity_;
  std::shared_ptr<VerticalImplicit> implicit_;
  std::shared_ptr<SourceRegistry> sources_;
  std::shared_ptr<SeamExchange> seams_;
};

}  // namespace snap
