#pragma once
// V3 lane C skeleton (declarations only; not built). One RiemannSolver
// module; the solver is a kind, not a class (6 classes today). All six kinds
// stay. hllc, lmars, roe, shallow-roe: one face kernel each in
// riemann_kernels.h for CPU and CUDA (MPS: CPU kernel on host copies, FOR
// CHENG). upwind, plume-roe: torch formulas, one definition on every backend.

namespace snap {

enum class RiemannKind : int { hllc, lmars, roe, shallow_roe, upwind, plume_roe };

struct RiemannSolverOptionsImpl {
  ADD_ARG(std::string, type) = "hllc";  // proposed single default (FOR CHENG)
  ADD_ARG(std::string, dir) = "omni";   // shallow-roe only
};

//! Lane R rev 2.2 (v3-design/R 4c59162a, header rev 4.2): flux = slot(d,
//! "riemann") in place, then post_slot; parts through part_slot() in place.
//! Frame: coord's flux2global<d>_ (x2/x3 in panel face basis). Per unit face
//! area; the register's divergence applies face_area<d>. Dtypes are lane X's
//! PrecisionPolicy rows (X.rst section 6). Storage: register slots only.
struct FaceFlux {
  torch::Tensor flux;          // (nvar, nc3, nc2, nc1), Quantity::kFlux
  torch::Tensor pressure;      // x1: part_slot(1, "riemann.pstar"), TOTAL p*,
                               // kGauge (FP64); none for shallow water
  torch::Tensor central;  // part_slot(d, "riemann.central") if requested @2/@3:
                          // ONE row, dry + species, 1/2 (F_L+F_R), post-solid
                          // states, kFlux; hllc/lmars/roe/sw only
  torch::Tensor wave_speed;    // optional, max |S| per face
  torch::Tensor events;        // optional uint8: bit0 p* clamped (hllc)
};
inline constexpr char const* kRiemannIncrement = "riemann";

//! face inputs the kinds read, from one EOS pass on TOTAL states
struct FaceThermo {
  torch::Tensor e, gamma, c;  // (2, ...) per side; lmars uses e / rho
};

//! the split (perturbation) entry, hllc only (M3): pressure rows of wl/wr
//! are perturbations about one face background p0; momentum flux uses them,
//! wave speeds and energy use totals; pressure out is the perturbation and
//! the sweep adds p0 in one place before posting.
struct FaceBackground {
  torch::Tensor p0;
};

class RiemannSolverImpl : public torch::nn::Cloneable<RiemannSolverImpl> {
 public:
  RiemannSolverOptions options;
  RiemannKind kind;
  //! states in the global frame; rotated in place by coord's helper (S)
  //! out.flux is reg.slot(d, "riemann"); out.central a part_slot view
  void forward(torch::Tensor wl, torch::Tensor wr, int dim, FaceFlux& out,
               FaceBackground const* bg = nullptr);
};

template <typename T>
struct FaceOut;        // pointers to the FaceFlux slots present, or null
struct RiemannParams;  // roe ideal-moist tables; dir for shallow-roe
//! one kernel per kind, one face (riemann_kernels.h)
template <RiemannKind K, typename T>
DISPATCH_MACRO void riemann_face(T const* wl, T const* wr, T const* thermo,
                                 int dim, int ny, int stride, T p0,
                                 FaceOut<T> out);

//! one dispatch stub; CPU loop and CUDA gpu_kernel switch on kind once
using riemann_fn = void (*)(at::TensorIterator& iter, RiemannKind kind,
                            int dim, RiemannParams const& params);

}  // namespace snap
