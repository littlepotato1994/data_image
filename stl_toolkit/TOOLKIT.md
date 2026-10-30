# Local STL job contract

Use only the job workspace and its attached images. Network access and package installation are forbidden.

Before modeling, inspect available Python packages. Typical useful packages are `numpy`, `scipy`, `scikit-image`, `trimesh`, `manifold3d`, `Pillow`, and `matplotlib`. If unavailable, use standard-library STL writers and a voxel or parametric mesh approach.

Modeling requirements:

- Coordinate system: X width, Y depth with +Y forward, Z up. Units are millimetres.
- Build one real volumetric object. Union connected parts and remove internal faces.
- Preserve genuine holes such as the integrated eyelet. Exclude detachable metal hardware.
- Reinforce fragile fingers, ankles, cape edges, small decorations, and the eyelet root conservatively.
- Do not add slicer supports to the STL.
- Express painted details through restrained relief or engraving only where useful for a single-colour print.
- Export canonical binary STL.

Validation requirements:

- Re-read the exported STL rather than checking an in-memory pre-export mesh.
- Measure W, D, H and triangle count.
- Check edge incidence, winding, degenerate and duplicate faces, connected surface components, positive volume, and the eyelet opening.
- State `unverified` for any checks not actually executed, including physical print success.
- Render previews from the final STL triangles, using identical scale for front, back, and oblique views.

Every required output belongs in `./output` with the exact names stated in the Codex task.

