import pandas as pd, torch, torch_geometric as tg
from ..core.file import NuMLFile
from ..labels import *
from ..graph import *

def single_plane_graph(out, key, hit, part, edep, l=ccqe.hit_label, e=edges.delaunay):
  """Process an event into graphs"""

  import os.path as osp
  if osp.exists(f"/data/uboone/pandora/processed_delaunay/r{key[0]}_sr{key[1]}_evt{key[2]}_p0.pt"):
    print(f"skipping {key}")
    return

  # skip any events with no simulated hits
  if (hit.index==key).sum() == 0: return
  if (edep.index==key).sum() == 0: return

  # get energy depositions, find max contributing particle, and ignore any evt_hits with no truth
  evt_edep = edep.loc[key].reset_index(drop=True)
  evt_edep = evt_edep.loc[evt_edep.groupby("hit_id")["energy_fraction"].idxmax()]
  evt_hit = evt_edep.merge(hit.loc[key].reset_index(), on="hit_id", how="inner").drop("energy_fraction", axis=1)

  # skip events with fewer than 50 simulated hits in any plane
  for i in range(3):
    if (evt_hit.global_plane==i).sum() < 50: return

  # get labels for each evt_particle
  evt_part = part.loc[key].reset_index(drop=True)
  evt_part = l(evt_part)

  # join the dataframes to transform evt_particle labels into hit labels
  evt_hit = evt_hit.merge(evt_part.drop(["parent_id", "type"], axis=1), on="g4_id", how="inner")

  # draw graph edges
  for p, plane in evt_hit.groupby("local_plane"):

    # Reset indices
    plane = plane.reset_index(drop=True).reset_index()

    pos = plane[["global_wire", "global_time"]].values / torch.tensor([0.5, 0.075])[None, :].float()
    node_feats = ["global_plane", "global_wire", "global_time", "tpc",
      "local_plane", "local_wire", "local_time", "integral", "rms"]
    data = tg.data.Data(
      x=torch.tensor(plane[node_feats].values).float(),
      y=torch.tensor(plane["label"].values).long(),
      pos=pos,
    )
    data = e(data)

    fname = f"r{key[0]}_sr{key[1]}_evt{key[2]}_p{p}"
    print("saving graph", fname)
    out.save(data, fname)

def process_file(out, fname, g=single_plane_graph, l=ccqe.hit_label, e=edges.delaunay, p=None):
  """Process all events in a file into graphs"""
  print(f"Processing {fname}")
  f = NuMLFile(fname)

  evt = f.get_dataframe("event_table", ["event_id"])
  hit = f.get_dataframe("hit_table")
  part = f.get_dataframe("particle_table", ["event_id", "g4_id", "parent_id", "type"])
  edep = f.get_dataframe("edep_table")

  # loop over events in file
  for key in evt.index: g(out, key, hit, part, edep, l, e)

  print('End processing ', fname)

