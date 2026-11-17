#pragma once
// V3 lane C skeleton (declarations only; not built). One direction-generic
// face flux in place of the x2 and x3 copies (hydro_forward.cpp:1088-1152)
// and of the x2/x3 reconstruction blocks (:1010-1031). x1 adds its
// reference hooks; the stage order is unchanged.

namespace snap {

//! what differs between directions; everything else is shared
struct FaceDir {
  int dim;               // DIM1 = 3, DIM2 = 2, DIM3 = 1
  int slot;              // index into the register and _cov_* arrays
  int seam_tag;          // x1_seam_rows tags 0x7730 (x2), 0x7734 (x3)
  bool disabled;         // disable-flux-x<n>
  torch::Tensor* flux;   // _flux1/_flux2/_flux3
  torch::Tensor* p_bg;   // pressure_base<n> (split path)
};

//! reconstruct -> [x1: WellBalancedX1] -> FaceFloor -> immersed solid ->
//! covariance (x2/x3) -> Riemann -> register. Cubed-sphere face-state
//! exchange stays between reconstruct and solve (lane S owns its calls).
FaceFlux sweep(HydroImpl& hydro, FaceDir const& dir, torch::Tensor const& w,
               Variables const& other);

}  // namespace snap
