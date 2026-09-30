"""Preview PNGs: STEP as an isometric shaded view (tessellation + matplotlib), DXF via ezdxf's drawing add-on."""
import io

import matplotlib

matplotlib.use("Agg")  # no GUI
import matplotlib.pyplot as plt  # noqa: E402


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def render_shape(shape) -> bytes:
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    verts, tris = shape.tessellate(0.1, 0.3)
    pts = [(v.x, v.y, v.z) for v in verts]
    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(projection="3d")
    ax.add_collection3d(Poly3DCollection([[pts[i] for i in t] for t in tris],
                                         facecolors="#9fb4c8", shade=True))
    bb = shape.BoundingBox()
    half = max(bb.xlen, bb.ylen, bb.zlen) / 2
    for setter, c in ((ax.set_xlim, bb.center.x), (ax.set_ylim, bb.center.y), (ax.set_zlim, bb.center.z)):
        setter(c - half, c + half)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=30, azim=-45)  # isometric-like
    ax.set_axis_off()
    return _png(fig)


def render_dxf(doc) -> bytes:
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_axes([0, 0, 1, 1])
    config = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.BLACK)
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=config).draw_layout(doc.modelspace())
    return _png(fig)
