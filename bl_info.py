# -*- coding: utf-8 -*-
bl_info = {
    "name": "LowHigh Renamer Extended",
    "author": "Insaanesh",
    "version": (1, 2, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > LowHigh",
    "description": "Tools for LOW/HIGH naming, copying and bake preparation",
    "category": "Object",
}

import bpy
import re
from bpy.props import StringProperty, BoolProperty


def clean_name(name):
    return re.sub(r'(_low|_high)$', '', name, flags=re.IGNORECASE)


def ensure_collection(name):
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def rename_object_and_mesh(obj, suffix):
    base = clean_name(obj.name)
    obj.name = base + "_" + suffix
    if obj.data and hasattr(obj.data, "name"):
        obj.data.name = base + "_" + suffix + "_mesh"


def move_objects_to_collection(objs, collection):
    for ob in objs:
        if ob.name not in collection.objects:
            collection.objects.link(ob)
        for coll in list(ob.users_collection):
            if coll != collection:
                try:
                    coll.objects.unlink(ob)
                except:
                    pass


class LHR_OT_rename_selected(bpy.types.Operator):
    bl_idname = "lhr.rename_selected"
    bl_label = "Rename Selected"
    bl_options = {"REGISTER", "UNDO"}

    suffix: StringProperty(default="_low")
    mode: StringProperty(default="ADD")

    def execute(self, context):
        sel = context.selected_objects
        if not sel:
            self.report({"WARNING"}, "No selection")
            return {"CANCELLED"}

        for ob in sel:
            if self.mode == "ADD":
                rename_object_and_mesh(ob, self.suffix.strip("_"))
            elif self.mode == "REMOVE":
                base = clean_name(ob.name)
                ob.name = base
                if ob.data:
                    ob.data.name = base + "_mesh"

        return {"FINISHED"}

class LHR_OT_copy_to_low(bpy.types.Operator):
    """Duplicate selected objects, move copies to LOW collection and rename them"""
    bl_idname = "lhr.copy_to_low"
    bl_label = "Copy to LOW"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        low_col = ensure_collection("LOW")
        created = []

        for src in context.selected_objects:
            # copy object and its data
            new_obj = src.copy()
            if src.data:
                try:
                    new_obj.data = src.data.copy()
                except Exception:
                    pass

            # ensure the copy is NOT linked to scene master collection:
            # do NOT call bpy.context.scene.collection.objects.link(new_obj)
            # instead link only to the target collection
            if new_obj.name not in low_col.objects:
                low_col.objects.link(new_obj)

            # remove links to any other collections except the target (safety)
            for coll in list(new_obj.users_collection):
                if coll != low_col:
                    try:
                        coll.objects.unlink(new_obj)
                    except Exception:
                        pass

            # clean and rename mesh+object
            rename_object_and_mesh(new_obj, scn.lhr_suffix_low.strip('_'))
            created.append(new_obj)

        self.report({'INFO'}, f"Copied {len(created)} objects to LOW collection")
        return {'FINISHED'}


class LHR_OT_copy_to_high(bpy.types.Operator):
    """Duplicate selected objects, move copies to HIGH collection and rename them"""
    bl_idname = "lhr.copy_to_high"
    bl_label = "Copy to HIGH"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        high_col = ensure_collection("HIGH")
        created = []

        for src in context.selected_objects:
            new_obj = src.copy()
            if src.data:
                try:
                    new_obj.data = src.data.copy()
                except Exception:
                    pass

            # link only to HIGH collection (avoid scene.collection linking)
            if new_obj.name not in high_col.objects:
                high_col.objects.link(new_obj)

            # unlink other collection links (keep only HIGH)
            for coll in list(new_obj.users_collection):
                if coll != high_col:
                    try:
                        coll.objects.unlink(new_obj)
                    except Exception:
                        pass

            rename_object_and_mesh(new_obj, scn.lhr_suffix_high.strip('_'))
            created.append(new_obj)

        self.report({'INFO'}, f"Copied {len(created)} objects to HIGH collection")
        return {'FINISHED'}


class LHR_OT_find_pairs(bpy.types.Operator):
    bl_idname = "lhr.find_pairs"
    bl_label = "Find LOW/HIGH pairs"

    def execute(self, context):
        scn = context.scene
        objs = bpy.data.objects
        groups = {}

        for ob in objs:
            base = clean_name(ob.name)
            groups.setdefault(base, []).append(ob)

        found = []

        for base, group in groups.items():
            low = None
            high = None
            for ob in group:
                if ob.name.lower().endswith(scn.lhr_suffix_low.lower()):
                    low = ob
                if ob.name.lower().endswith(scn.lhr_suffix_high.lower()):
                    high = ob
            if low and high:
                found.append((base, low, high))

        if scn.lhr_create_collections:
            if scn.lhr_common_collection:
                col = ensure_collection("Bake_Pairs")
                for base, low, high in found:
                    move_objects_to_collection([low, high], col)
            else:
                for base, low, high in found:
                    col = ensure_collection("Bake_" + base)
                    move_objects_to_collection([low, high], col)

        self.report({"INFO"}, f"Found {len(found)} pairs")
        return {"FINISHED"}


class LHR_OT_prepare_for_bake(bpy.types.Operator):
    bl_idname = "lhr.prepare_for_bake"
    bl_label = "Prepare for Bake"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scn = context.scene
        sel = context.selected_objects
        if not sel:
            return {"CANCELLED"}

        for ob in sel:
            if ob.type != "MESH":
                continue

            if scn.lhr_apply_scale:
                bpy.context.view_layer.objects.active = ob
                bpy.ops.object.transform_apply(scale=True)

            if scn.lhr_set_origin:
                bpy.context.view_layer.objects.active = ob
                bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY")

            if scn.lhr_triangulate:
                mod = ob.modifiers.new("LHR_Triangulate", "TRIANGULATE")
                mod.keep_customdata = True

        if scn.lhr_hide_others:
            for o in bpy.data.objects:
                if o not in sel:
                    o.hide_viewport = True

        return {"FINISHED"}


class LHR_OT_clean_collections(bpy.types.Operator):
    bl_idname = "lhr.clean_collections"
    bl_label = "Clean bake collections"

    def execute(self, context):
        removed = 0
        for col in list(bpy.data.collections):
            if col.name.startswith("Bake_") and not col.objects:
                bpy.data.collections.remove(col)
                removed += 1
        self.report({"INFO"}, f"Removed {removed} collections")
        return {"FINISHED"}


class LHR_PT_panel(bpy.types.Panel):
    bl_idname = "LHR_PT_panel"
    bl_label = "LowHigh Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LowHigh"

    def draw(self, context):
        scn = context.scene
        layout = self.layout

        layout.label(text="Suffixes:")
        row = layout.row()
        row.prop(scn, "lhr_suffix_low", text="Low")
        row.prop(scn, "lhr_suffix_high", text="High")

        layout.separator()
        layout.label(text="Rename:")
        row = layout.row()
        op = row.operator("lhr.rename_selected", text="Add Low")
        op.suffix = scn.lhr_suffix_low
        op.mode = "ADD"

        op = row.operator("lhr.rename_selected", text="Add High")
        op.suffix = scn.lhr_suffix_high
        op.mode = "ADD"

        op = layout.operator("lhr.rename_selected", text="Remove Suffix")
        op.mode = "REMOVE"
        op.suffix = ""

        layout.separator()
        layout.label(text="Copy:")
        row = layout.row()
        row.operator("lhr.copy_to_low")
        row.operator("lhr.copy_to_high")

        layout.separator()
        layout.label(text="Pairs:")
        layout.operator("lhr.find_pairs")
        layout.prop(scn, "lhr_create_collections")
        layout.prop(scn, "lhr_common_collection")

        layout.separator()
        layout.label(text="Bake Prep:")
        layout.prop(scn, "lhr_apply_scale")
        layout.prop(scn, "lhr_triangulate")
        layout.prop(scn, "lhr_set_origin")
        layout.prop(scn, "lhr_hide_others")
        layout.operator("lhr.prepare_for_bake")

        layout.separator()
        layout.operator("lhr.clean_collections")


classes = (
    LHR_OT_rename_selected,
    LHR_OT_copy_to_low,
    LHR_OT_copy_to_high,
    LHR_OT_find_pairs,
    LHR_OT_prepare_for_bake,
    LHR_OT_clean_collections,
    LHR_PT_panel,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.lhr_suffix_low = StringProperty(default="_low")
    bpy.types.Scene.lhr_suffix_high = StringProperty(default="_high")

    bpy.types.Scene.lhr_create_collections = BoolProperty(default=True)
    bpy.types.Scene.lhr_common_collection = BoolProperty(default=False)

    bpy.types.Scene.lhr_apply_scale = BoolProperty(default=True)
    bpy.types.Scene.lhr_triangulate = BoolProperty(default=False)
    bpy.types.Scene.lhr_set_origin = BoolProperty(default=False)
    bpy.types.Scene.lhr_hide_others = BoolProperty(default=True)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

    del bpy.types.Scene.lhr_suffix_low
    del bpy.types.Scene.lhr_suffix_high
    del bpy.types.Scene.lhr_create_collections
    del bpy.types.Scene.lhr_common_collection
    del bpy.types.Scene.lhr_apply_scale
    del bpy.types.Scene.lhr_triangulate
    del bpy.types.Scene.lhr_set_origin
    del bpy.types.Scene.lhr_hide_others


if __name__ == "__main__":
    register()
