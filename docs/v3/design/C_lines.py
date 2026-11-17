"""Lane C file-by-file line budget, revision 4: every solver and scheme kept. 'now' is measured (git show <pin>:<file> | wc -l);
'after' is a design estimate. Run from the snapy clone."""
import subprocess, csv, sys
PIN = "9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410"
def now(path, lo=None, hi=None):
    txt = subprocess.run(["git", "show", f"{PIN}:{path}"], capture_output=True, text=True, check=True).stdout
    n = txt.count("\n")
    return n if lo is None else hi - lo + 1
# (file, after, fate) ; after=0 means removed or merged elsewhere
SPEC = [
 # recon
 ("src/recon/cp3.cpp",0,"merged: table -> x1_rows.cpp, calls -> reconstruct.cpp"),
 ("src/recon/cp5.cpp",0,"merged: table -> x1_rows.cpp, calls -> reconstruct.cpp"),
 ("src/recon/interp_impl.cuh",0,"merged -> recon_line.cuh (Op wrappers, interp_nu_untiled deleted)"),
 ("src/recon/interp_impl.h",0,"deleted: line loops are the CPU loop in recon_dispatch.cpp"),
 ("src/recon/interp_point.h",0,"renamed -> recon_point.h (all point functions kept)"),
 ("src/recon/interpolation.cpp",0,"deleted: factory -> Scheme parse in reconstruct.cpp"),
 ("src/recon/interpolation.hpp",0,"deleted: 7 Interp classes -> Scheme + ReconRows"),
 ("src/recon/plm.cpp",0,"merged -> reconstruct.cpp (torch ops kept)"),
 ("src/recon/ppm.cpp",0,"merged -> reconstruct.cpp (ppm kept; not implemented at the pin, as today)"),
 ("src/recon/recon_dispatch.cpp",70,"MPS rewrites :83-158 deleted (OnHost); one stub"),
 ("src/recon/recon_dispatch.cu",70,"one launcher for uniform and per-face rows"),
 ("src/recon/recon_dispatch.hpp",15,"one dispatch stub"),
 ("src/recon/recon_dispatch_nu.cpp",0,"deleted: second path"),
 ("src/recon/recon_dispatch_nu.cu",0,"deleted: second path"),
 ("src/recon/recon_dispatch_nu.hpp",0,"deleted: second path"),
 ("src/recon/recon_launch.cuh",0,"merged -> recon_line.cuh"),
 ("src/recon/reconstruct.cpp",165,"dead block :118-141 and floors removed; plm, ppm stub, Scheme parse and group table added"),
 ("src/recon/reconstruct.hpp",60,"dead options is_boundary_*, limiter removed"),
 ("src/recon/weno3.cpp",0,"merged: table -> x1_rows.cpp, calls -> reconstruct.cpp"),
 ("src/recon/weno5.cpp",0,"merged: table -> x1_rows.cpp"),
 ("src/recon/x1_coeffs.cpp",0,"merged -> x1_rows.cpp"),
 ("src/recon/x1_coeffs.hpp",0,"merged -> x1_rows.hpp"),
 ("src/recon/x1_coeffs_device.h",0,"merged -> recon_point.h traits"),
 # riemann
 ("src/riemann/hllc.cpp",0,"merged -> riemann.cpp (one forward)"),
 ("src/riemann/hllc_dispatch.cpp",0,"CPU loop -> riemann_dispatch.cpp; MPS :50-164 deleted"),
 ("src/riemann/hllc_impl.h",0,"moved -> riemann_kernels.h"),
 ("src/riemann/lmars.cpp",0,"merged -> riemann.cpp"),
 ("src/riemann/lmars_dispatch.cpp",0,"CPU loop -> riemann_dispatch.cpp; MPS :44-102 deleted"),
 ("src/riemann/lmars_impl.h",0,"moved -> riemann_kernels.h"),
 ("src/riemann/plume_roe.cpp",45,"kept as tensor code; writes its slot; unused Roe averages, Jacobian and polynomial (:57-92) dropped"),
 ("src/riemann/riemann_dispatch.cu",65,"one CUDA loop switching on kind (hllc, lmars, roe, shallow-roe)"),
 ("src/riemann/riemann_dispatch.hpp",0,"merged -> riemann.hpp"),
 ("src/riemann/riemann_solver.cpp",0,"-> riemann.cpp (incl. upwind); rotation :12-47 -> coord (lane S)"),
 ("src/riemann/riemann_solver.hpp",0,"-> riemann.hpp; 6 classes -> 1"),
 ("src/riemann/roe.cpp",0,"merged -> riemann.cpp (ideal-moist params in RiemannParams)"),
 ("src/riemann/roe_dispatch.cpp",0,"CPU loop -> riemann_dispatch.cpp; MPS :50-219 deleted"),
 ("src/riemann/roe_impl.h",0,"moved -> riemann_kernels.h"),
 ("src/riemann/shallow_roe.cpp",0,"merged -> riemann.cpp"),
 ("src/riemann/shallow_roe_dispatch.cpp",0,"CPU loop -> riemann_dispatch.cpp; MPS :33-81 deleted"),
 ("src/riemann/shallow_roe_impl.h",0,"moved -> riemann_kernels.h"),
 # reference
 ("src/hydro/hydro_ref_x1_impl.h",290,"kept; stretched rows read from x1_rows table"),
 ("src/hydro/hydro_reference.hpp",0,"-> x1_reference.hpp"),
 ("src/hydro/wb_ref4.cpp",0,"rows -> x1_rows.cpp; flag/faces -> x1_reference.cpp"),
 ("src/hydro/wb_ref4.hpp",0,"-> x1_rows.hpp, x1_reference.hpp"),
 ("src/hydro/balance_column.cpp",105,"order-4 pass uses Conversion and X1Reference"),
 ("src/hydro/balance_column.hpp",110,"contract kept"),
 ("src/hydro/split_reference_scalar.hpp",74,"unchanged"),
 ("src/hydro/hydro_dispatch.cpp",0,"-> x1_reference_dispatch.cpp; MPS :33-54, :101-275 deleted; rows :277-312 -> x1_rows"),
 ("src/hydro/hydro_dispatch.cu",0,"-> x1_reference_dispatch.cu"),
 ("src/hydro/hydro_dispatch.hpp",0,"-> x1_reference_dispatch.hpp; wall4/conv4 decls -> recon"),
]
MOVED = [  # lane R ranges whose code moves into lane C files
 ("src/hydro/hydro_forward.cpp",291,368,"conv4 weights, wall4 weights/fill, admissibility -> x1_rows, conversion"),
 ("src/hydro/hydro_forward.cpp",417,504,"conversion-order 4 stage -> conversion.cpp"),
 ("src/hydro/hydro_forward.cpp",668,820,"well-balanced x1 block -> well_balanced_x1.cpp"),
 ("src/hydro/hydro.cpp",605,872,"_hydro_ref_x1 -> x1_reference.cpp"),
]
NEW = [
 ("src/recon/recon_point.h",125),("src/recon/recon_line.cuh",165),
 ("src/recon/x1_rows.hpp",45),("src/recon/x1_rows.cpp",260),
 ("src/recon/conversion.hpp",30),("src/recon/conversion.cpp",100),
 ("src/recon/well_balanced_x1.hpp",20),("src/recon/well_balanced_x1.cpp",100),
 ("src/recon/face_floor.hpp",25),("src/recon/face_floor.cpp",25),
 ("src/riemann/riemann.hpp",110),("src/riemann/riemann.cpp",175),
 ("src/riemann/riemann_kernels.h",525),("src/riemann/riemann_dispatch.cpp",60),
 ("src/hydro/x1_reference.hpp",70),("src/hydro/x1_reference.cpp",230),
 ("src/hydro/x1_reference_dispatch.hpp",35),("src/hydro/x1_reference_dispatch.cpp",65),
 ("src/hydro/x1_reference_dispatch.cu",95),
]
rows=[]; tn=ta=0
for f,a,fate in SPEC:
    n=now(f); tn+=n; ta+=a; rows.append((f,n,a,fate))
mv=0
for f,lo,hi,fate in MOVED:
    n=now(f,lo,hi); mv+=n; rows.append((f"{f}:{lo}-{hi}",n,0,"lane R range, moved in: "+fate))
nw=0
for f,a in NEW:
    nw+=a; rows.append((f,0,a,"new lane C file"))
w=csv.writer(sys.stdout); w.writerow(["file","lines_now_measured","lines_after_estimate","fate"])
for r in rows: w.writerow(r)
after=ta+nw
w.writerow(["TOTAL baseline files",tn,ta,""]); w.writerow(["TOTAL moved in from lane R",mv,0,""]); w.writerow(["TOTAL new files",0,nw,""])
w.writerow(["TOTAL lane C",tn+mv,after,f"{(after-tn)/tn*100:.1f}% vs baseline; {(after-tn-mv)/(tn+mv)*100:.1f}% vs baseline+moved"])
