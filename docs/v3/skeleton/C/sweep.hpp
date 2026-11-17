#pragma once
// V3 lane C skeleton (declarations only; not built). One direction-generic
// face flux in place of the x2 and x3 copies (hydro_forward.cpp:1088-1152)
// and of the x2/x3 reconstruction blocks (:1010-1031). x1 adds its
// reference hooks; the stage order is unchanged. No face-flux storage here:
// the solve writes into the register's slot for (direction, stage).

namespace snap {

class FluxRegister;  // lane R rev 2.2, header rev 4.2 (4c59162a)

//! what differs between directions; everything else is shared
struct FaceDir {
  int dim;       // DIM1 = 3, DIM2 = 2, DIM3 = 1
  int seam_tag;  // x1_seam_rows tags 0x7730 (x2), 0x7734 (x3)
  bool disabled; // disable-flux-x<n>
};

//! split in two because the cubed-sphere face-state exchange (lane S)
//! runs between reconstruction and solve for x2 and x3 together
FaceStates reconstruct_faces(HydroImpl& hydro, FaceDir const& dir,
                             torch::Tensor const& w, Variables const& other);
//! sweep: FaceFloor -> solid -> before_solve(faces, d) -> rotate -> Riemann
//! into slot(d, "riemann"), post_slot, part slots. R-C1 (R rev 2.2): R builds
//! its covariance in before_solve from post-solid, unrotated faces; no copy
using FaceHook = std::function<void(FaceStates const&, int)>;
void solve_faces(HydroImpl& hydro, FaceDir const& dir, FaceStates& faces,
                 FluxRegister& reg, FaceHook const& before_solve = {});

}  // namespace snap
