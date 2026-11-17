#pragma once
// V3 lane C skeleton (declarations only; not built). Replaces interp_point.h,
// interp_impl.h and the per-scheme classes of interpolation.hpp. One
// definition per scheme; CPU and CUDA call these, MPS runs the CPU kernel on
// host copies (OnHost, src/utils/on_host.hpp). dc and plm stay torch ops.
// Removed: ppm (throws), weno3 and cp3 (no deck uses them).

namespace snap {

enum class Scheme : int { dc, plm, cp5, weno5 };

//! stencil width and coefficient-row length of each scheme; a row of a
//! per-face table and the uniform table have the same layout, so weno5's
//! three linear weights d sit after its nine stencil rows in both
template <Scheme S>
struct SchemeTraits;  // {int stencil; int ncoeff; bool nonlinear;}

//! one face from the stencil at src (inputs stride apart) and one row c of
//! the scheme's table. Constants are typed T (FP32 stays FP32: PR C9).
template <typename T, int N>
DISPATCH_MACRO T poly_point(T const* src, int stride, T const* c);

template <typename T>
DISPATCH_MACRO T weno5_point(T const* src, int stride, T const* c, bool scale);

//! the line loop body shared by the CPU loop and the CUDA line kernel
template <Scheme S, typename T>
DISPATCH_MACRO T recon_point(T const* src, int stride, T const* row,
                             bool scale);

}  // namespace snap
