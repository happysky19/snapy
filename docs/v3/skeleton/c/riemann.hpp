#pragma once
// V3 lane C skeleton (declarations only; not built). One RiemannSolver
// module; the solver is a kind, not a class (6 classes today). One kernel
// per kind in riemann_kernels.h for CPU and CUDA; MPS runs the CPU kernel
// on host copies. plume-roe and the hydro use of upwind are removed.

namespace snap {

enum class RiemannKind : int { hllc, lmars, roe, shallow_roe };

struct RiemannSolverOptionsImpl {
  ADD_ARG(std::string, type) = "hllc";  // the single default
  ADD_ARG(std::string, dir) = "omni";   // shallow-roe only
};

//! what a solve hands to the register (lane A). Undefined optional
//! tensors are not computed. All rows in the global frame.
struct FaceFlux {
  torch::Tensor flux;          // (nvar, ...) conserved-variable flux
  torch::Tensor pressure;      // (...) TOTAL face pressure p*; none for SW
  torch::Tensor mass_central;  // (1+ny, ...) 1/2 (F_L + F_R), dry + species
  torch::Tensor wave_speed;    // (...) max |S| of the face (CFL, diagnostics)
  torch::Tensor events;        // uint8 (...) bit0 p* clamped, bit1 Roe LLF
};
//! dissipative mass flux = flux[mass rows] - mass_central

//! face inputs the kinds read, from one EOS pass on TOTAL states
struct FaceThermo {
  torch::Tensor e, gamma, c;  // (2, ...) per side; lmars uses e / rho
};

//! the split (perturbation) entry, hllc only: pressure rows of wl/wr are
//! perturbations about one shared face background p0 (M3). Momentum flux
//! uses perturbations; wave speeds and energy use totals; pressure out is
//! the perturbation and the caller adds p0 (one place, the sweep).
struct FaceBackground {
  torch::Tensor p0;
};

class RiemannSolverImpl : public torch::nn::Cloneable<RiemannSolverImpl> {
 public:
  RiemannSolverOptions options;
  RiemannKind kind;
  //! states in the global frame; rotated in place with lane S's helper
  void forward(torch::Tensor wl, torch::Tensor wr, int dim, FaceFlux& out,
               FaceBackground const* bg = nullptr);
  //! legacy signature for tests and Python: returns out.flux
  torch::Tensor forward(torch::Tensor wl, torch::Tensor wr, int dim,
                        torch::Tensor flx, torch::Tensor face_pressure = {});
};

//! one kernel per kind, one face (riemann_kernels.h). Face is a pointer +
//! stride view; Out writes the FaceFlux slots that are present.
template <typename T>
struct FaceOut;       // pointers to flux/pressure/central/speed/events or null
struct RiemannParams; // ideal-moist tables for roe, dir for shallow-roe
template <RiemannKind K, typename T>
DISPATCH_MACRO void riemann_face(T const* wl, T const* wr, T const* thermo,
                                 int dim, int ny, int stride, T p0,
                                 FaceOut<T> out);

//! one dispatch stub; CPU loop and CUDA gpu_kernel switch on kind once
using riemann_fn = void (*)(at::TensorIterator& iter, RiemannKind kind,
                            int dim, RiemannParams const& params);

//! scalar transport (not a Riemann solver): donor-cell upwind flux
torch::Tensor upwind_flux(torch::Tensor const& ql, torch::Tensor const& qr,
                          torch::Tensor const& mass_flux);

}  // namespace snap
