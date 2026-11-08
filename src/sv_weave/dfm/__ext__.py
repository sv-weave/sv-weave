"""dv-flow-mgr extension: registers the ``svweave`` package."""
import os


def dvfm_packages():
    dfm_dir = os.path.dirname(os.path.abspath(__file__))
    return {
        "svweave": os.path.join(dfm_dir, "flow.dv"),
    }
