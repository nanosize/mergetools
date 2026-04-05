# Blender Merge Tool

This repository now contains only the `mesh_merge_tool` add-on for Blender 5.0.

![](https://i.imgur.com/EQ0rLzV.gif)

## Installation

Install [`mesh_merge_tool.zip`](./mesh_merge_tool.zip) from Blender Preferences > Add-ons > Install, then enable `Merge Tool`.

If Blender keeps loading an older copy, remove the existing add-on folder first:

`C:\Users\nanos\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\mesh_merge_tool`

Then reinstall the zip and restart Blender.

## Blender 5.0 notes

- `bl_info` targets Blender 5.0.
- Operator runtime state is initialized in `invoke()` instead of `__init__()` to avoid `StructRNA` lifecycle errors.
- Dashed-line shader creation is delayed until draw time so the add-on can still be imported in Blender background mode.

## Usage

In Edit Mode, activate the Merge Tool from the 3D Viewport toolbar.

![](https://i.imgur.com/EuHTXth.png)

You can also hotkey `mesh.merge_tool` in Blender Preferences > Keymap > 3D View > Mesh > Mesh (Global) if you want to invoke it directly without switching tools.

Click and hold the left mouse button on a vertex or edge, drag to a second vertex or edge, and release to merge.

- `1`, `A`, or `F` merges at the first component.
- `2` or `C` merges at the center.
- `3` or `L` merges at the last component.

In vertex mode, if there is an existing vertex selection and the tool starts on one of those vertices, the selection can be merged together at the chosen destination.

![](https://i.imgur.com/4SySLU5.gif)

Multi-merge, UV fixing, line width, point size, and colors are available from the add-on preferences.

![](https://i.imgur.com/hIgc9ly.png)

## Validation

The add-on is validated in Blender 5.0 by:

- registering and unregistering the tool from Blender CLI background mode
- verifying that `bpy.ops.mesh.merge_tool` is available after registration
