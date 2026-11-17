#pragma once
// V3 lane R skeleton: declarations only, in no build. PROVISIONAL (R.rst
// rev 1.1, section 3). Pin chengcli/snapy 9e5de2d4. What HydroImpl::forward
// (hydro_forward.cpp:370-1696) becomes: one stage driver that calls the
// lanes' ops in RegisterPhase order and owns no flux, no fixer and no
// AAM state. Lines the driver no longer holds are counted in R.rst s9.
#include <memory>
#include <vector>
#include <torch/torch.h>

#include "flux_register.hpp"

namespace snap {
class Sweep;               // lane C (sweep.hpp): recon + solve_faces
class PositivityLimiter;   // lane EF
class SedimentationPost;   // lane EF: add(1, "sedimentation", ...)
class GravityWork;         // lane I: G[M] reads the register's x1 mass
class VerticalImplicit;    // lane I: posts vic.*
class SourceRegistry;      // lane A: SourcePhase pre/post_implicit, split
class SeamExchange;        // lane S: moves the peer entry of shared faces
class SolidFaces;          // lane S: wall and immersed-solid mask, values

//! what one stage reads that R does not own; all borrowed, never stored
struct StageInputs {
  torch::Tensor u, w;  // hydro_u (kHydroState), hydro_w (kPrimitive)
  torch::Tensor solid;  // immersed solid mask or undefined
  double dt;            // X's host dt (step dt, never dt_corr)
  int stage;
};

//! the slimmed Hydro module: options parse, ownership and the stage driver
class HydroStage {
 public:
  //! the register request from the lanes' needs: A "riemann.central@2/3"
  //! in exact mode; I "vic.mass_total@1", "vic.mass_dry@1"; O step_field
  //! {1}; EF its counter names; scalars "covariance.dry@2/3" for EF's R4
  RegisterRequest request() const;

  //! sweep: x1, then x2/x3. C writes slot(d, "riemann") and the part slots;
  //! C's covariance and EF's sedimentation are add()s
  void sweep(StageInputs const& in, FluxRegister& reg);
  //! reconcile: x1 seam replace() (:868-946 today, process seams only),
  //! after sedimentation, before positivity; then apply_prescribed(d)
  void reconcile(FluxRegister& reg);
  //! limit: EF reads total(d) once, carry add()s in order, then scale()
  void limit(StageInputs const& in, FluxRegister& reg);
  //! divergence: du = -div(total) through coord, then the p* sources
  torch::Tensor divergence(StageInputs const& in, FluxRegister const& reg);
  //! pre_implicit: A's sources; gravity work on the limited x1 total
  void pre_implicit(StageInputs const& in, torch::Tensor du, FluxRegister& reg);
  //! implicit: I's solve with dt_corr = w2_s dt for 3+ stages (:1568-1583);
  //! posts divide by A_f dt with the step dt
  void implicit(StageInputs const& in, torch::Tensor du, FluxRegister& reg);
  //! post_implicit: apply_prescribed(1); A's m1 from A_f total(1) (today
  //! Phi, :1641, :1646); I's G remainder; tracer transfer from vic.mass_dry
  void post_implicit(StageInputs const& in, torch::Tensor du,
                     FluxRegister& reg);
  //! the whole stage in that order, then reg.end_stage(dt); returns du
  torch::Tensor forward(StageInputs const& in, FluxRegister& reg);
  //! after X's RK combine: step-end fixers (conserved limiter,
  //! meshblock.cpp:907-909; A's closure, :983-990) post cell_amount only
  void after_combine(torch::Tensor u, FluxRegister& reg);

 private:
  std::shared_ptr<Sweep> sweep_;
  std::shared_ptr<PositivityLimiter> limiter_;
  std::shared_ptr<SedimentationPost> sed_;
  std::shared_ptr<GravityWork> gravity_;
  std::shared_ptr<VerticalImplicit> implicit_;
  std::shared_ptr<SourceRegistry> sources_;
  std::shared_ptr<SeamExchange> seams_;
  std::shared_ptr<SolidFaces> solids_;
};

}  // namespace snap
