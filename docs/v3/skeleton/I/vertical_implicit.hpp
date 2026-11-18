#pragma once
// V3 lane I skeleton (declarations only; not part of any build).
// Design: docs/v3/design/I.rst. Pin 9e5de2d4. Replaces src/implicit/
// implicit_hydro.hpp.

#include <torch/nn/cloneable.h>
#include <yaml-cpp/yaml.h>
#include <snap/add_arg.h>

namespace snap {

class HydroImpl;
class GravityWork;      // gravity_work.hpp
class FluxRegister;     // lane R: docs/v3/skeleton/R/flux_register.hpp@4c59162a

//! The two VIC matrices; the value is the block size. Replaces the bit test
//! (scheme >> 3) & 1 of ImplicitOptionsImpl (implicit_hydro.hpp:37).
enum class VicMatrix : int { partial = 3, full = 5 };

//! Bits of each column's int32 status (I.rst s7), written by its thread; the
//! block status is their OR: flag_retry("implicit.column", any) (R.hpp:78).
enum VicStatusBit : int32_t {
  kVicInputNonfinite = 1,   //!< a column's du, w or gamma is not finite
  kVicSingular = 2,         //!< ludcmp found a singular block
  kVicResultNonfinite = 4,  //!< a nonfinite solution or redistribution
  kVicFp64Retried = 8,      //!< the column predicate ran the FP64 stage
  kVicFp64Failed = 16       //!< the FP64 retry failed too: redo the step
};

struct VerticalImplicitOptionsImpl {
  //! implicit-scheme: 1 -> partial, 9 -> full; 0/absent -> nullptr (no module)
  static std::shared_ptr<VerticalImplicitOptionsImpl> from_yaml(
      YAML::Node const& integration);

  ADD_ARG(VicMatrix, matrix) = VicMatrix::full;
  ADD_ARG(std::string, precision) = "auto";  //!< auto | float32 | float64
  ADD_ARG(bool, fallback_fp64) = true;       //!< per-column, on device
  ADD_ARG(double, advection_cfl) = 1.0;
  ADD_ARG(double, shear_cfl) = 0.0;
};
using VerticalImplicitOptions = std::shared_ptr<VerticalImplicitOptionsImpl>;

//! Fluid runs of each column (I.rst s3, note 15), rebuilt only when the solid
//! mask's version changes. Any mask: up to `nrun` runs per column, as the
//! pin's redistribution walks them. `single`: every column has one run that
//! reaches the top (no solid, or #369's floor); only then are the corrected-PE
//! wall rows the Woodbury rows k0 (first fluid), k1. Lane I's type; lane S
//! keeps PrescribedFaces; both from one solid mask and version (I.rst s3).
struct ColumnSegments {
  torch::Tensor lo, hi;      //!< [nc3, nc2, nrun] int: run [lo, hi), -1 unused
  torch::Tensor k0, k1;      //!< [nc3, nc2] int: Woodbury wall rows (single)
  int nrun = 1;
  bool single = true;
  int64_t mask_version = -1;  //!< the same version PrescribedFaces is built from
  static ColumnSegments whole(int nx1, torch::TensorOptions const& opts);
  //! from the solid mask and, for a floor, #369's X1Wall depth
  static ColumnSegments from_solid(torch::Tensor const& solid,
                                   HydroImpl const& hydro);
};

//! What one solve hands to lane R's FluxRegister in phase `implicit` (I.rst
//! s4). Face fields: x1 faces [is, ie], M / (A dt) at the step dt, before
//! stage weights, coord's flux2global1_ frame (R.hpp:4-5). Dim d = dir + 1.
struct VicIncrement {
  torch::Tensor mass_dry;    //!< add(1, "vic.mass_dry", {IDN}); also kept
  torch::Tensor mass_species;//!< add(1, "vic.mass_species", {ICY..})
  torch::Tensor momentum_t;  //!< add(1, "vic.momentum_t", {IVY, IVZ}); also
                             //!< kept (3rd part); scheme 9: bottom-up prefix sum
  torch::Tensor mass_total;  //!< keep(1, "vic.mass_total"): G's remainder
  torch::Tensor cell;        //!< cell_amount("vic.cell", V du, w2_s, cell_source)
                             //!< x1 momentum, energy (no gw), scheme-9 m_t
  torch::Tensor clamped;     //!< cell_amount("vic.mass_clamped", .., w2_s,
                             //!< flux_correction): V div(moved - requested)
  torch::Tensor momentum_top;//!< diagnostic amount, scheme 9: minus column sum
};
class VerticalImplicitImpl
    : public torch::nn::Cloneable<VerticalImplicitImpl> {
 public:
  static std::shared_ptr<VerticalImplicitImpl> create(
      VerticalImplicitOptions const& opts, torch::nn::Module* p,
      std::string const& name = "icorr");
  VerticalImplicitOptions options;
  HydroImpl const* phydro = nullptr;  //!< non-owning parent
  VerticalImplicitImpl();
  explicit VerticalImplicitImpl(VerticalImplicitOptions const& options,
                                torch::nn::Module* p = nullptr);
  void reset() override;
  //! Phase `implicit` of one stage. du: the explicit increment, G[M_exp]
  //! already in its energy row. dt: host double, the stage-weighted operator
  //! dt (hydro_forward.cpp:1568-1583), keyed in X's GraphKey (I.rst s7).
  //! Posts VicIncrement to reg (adds, keep, cell_amount). No host
  //! read: failures set col_status() bits only.
  void forward(torch::Tensor du, torch::Tensor w, torch::Tensor gamma,
               double dt, GravityWork const& gw,
               FluxRegister& reg, torch::Tensor const& solid = {});
  //! Phase post_implicit, after apply_prescribed(1), before A's m1 (I.rst s4):
  //! books G[kept vic.mass_total] - R dq into du's energy row (dq from du0).
  void book_remainder(torch::Tensor du, GravityWork const& gw,
                      FluxRegister const& reg) const;
  torch::Tensor col_status() const;  //!< [nc3, nc2] int32 VicStatusBit
  torch::Tensor status() const;      //!< 0-d OR-reduction of col_status
  void reset_status();
  //! output-only (lane O's `implicit` diagnostic, load_diag_output_data.cpp:220)
  torch::Tensor correction() const;
  //! meters as at the pin (implicit_hydro.hpp:94-99), accumulation dtype
  torch::Tensor clamp_residual() const;
  torch::Tensor dry_clamp_step() const;
  torch::Tensor fp64_fallbacks() const;
  //! on a redo only (the host already synchronised): log the failed columns
  void report_failure(std::ostream& os) const;
 private:
  //! scratch a, b, c, delta, z0, z1, du0, col_status: unregistered, allocated
  //! once per (shape, dtype, device): stable addresses for captured graphs
  void ensure_scratch(torch::Tensor const& w);
  VicIncrement _inc;
  ColumnSegments _seg;
  torch::Tensor _a, _b, _c, _delta, _z0, _z1, _du0, _col_status, _meters[3];
};
TORCH_MODULE(VerticalImplicit);

}  // namespace snap
