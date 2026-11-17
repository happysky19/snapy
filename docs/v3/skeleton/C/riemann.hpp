#pragma once
// V3 lane C skeleton (declarations only; not built). One RiemannSolver
// module; the solver is a kind, not a class (6 classes today). One kernel
// per kind in riemann_kernels.h for CPU and CUDA; MPS runs the CPU kernel
// on host copies. Removed: roe, plume-roe (no deck); upwind is scalar-only.

namespace snap {

enum class RiemannKind : int { hllc, lmars, shallow_roe };

struct RiemannSolverOptionsImpl {
  ADD_ARG(std::string, type) = "hllc";  // the single default
  ADD_ARG(std::string, dir) = "omni";   // shallow-roe only
};

//! The increment lane C posts to the flux register (lane R), one per
//! direction and RK stage, under the name "riemann". Frame: global
//! coordinate components (after coord's to_global_frame_). Area: per unit
//! face area; the register's divergence multiplies by face_area<d>.
//! Storage: fixed register slots, never a lane C buffer.
struct FaceFlux {
  torch::Tensor flux;          // (nvar, nc3, nc2, nc1); FP32 under FP32
  torch::Tensor pressure;      // x1 only: TOTAL face pressure p*, FP64; none
                               // for shallow water
  torch::Tensor mass_central;  // x2/x3, only with conserve-axial-momentum
                               // full: (1+ny) rows, FP64, 1/2 (F_L + F_R)
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
  //! out's tensors are views of register slots, written in place
  void forward(torch::Tensor wl, torch::Tensor wr, int dim, FaceFlux& out,
               FaceBackground const* bg = nullptr);
};

template <typename T>
struct FaceOut;        // pointers to the FaceFlux slots present, or null
struct RiemannParams;  // dir for shallow-roe
//! one kernel per kind, one face (riemann_kernels.h)
template <RiemannKind K, typename T>
DISPATCH_MACRO void riemann_face(T const* wl, T const* wr, T const* thermo,
                                 int dim, int ny, int stride, T p0,
                                 FaceOut<T> out);

//! one dispatch stub; CPU loop and CUDA gpu_kernel switch on kind once
using riemann_fn = void (*)(at::TensorIterator& iter, RiemannKind kind,
                            int dim, RiemannParams const& params);

}  // namespace snap
