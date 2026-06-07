# Notebooks

## `eda.ipynb` — exploratory data analysis

Profiles `Gamepass_Games_v1.csv` before enrichment to ground the design decisions.

### Reproduce

The base Anaconda env ships a pandas build incompatible with NumPy 2.x, so we use an isolated
venv + a registered Jupyter kernel named **`gpve`**:

```bash
# from repo root
python -m venv .venv
./.venv/Scripts/python -m pip install -r notebooks/requirements.txt   # Windows
# source .venv/bin/activate && pip install -r notebooks/requirements.txt   # macOS/Linux
./.venv/Scripts/python -m ipykernel install --user --name gpve --display-name "Python (gpve)"
```

Then either open `eda.ipynb` in Jupyter and select the **Python (gpve)** kernel, or run it
headless:

```bash
./.venv/Scripts/python -m jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.kernel_name=gpve notebooks/eda.ipynb
```

### What's inside

`446` unique games (from `455` raw rows; 9 duplicates/platform variants collapsed by the
cleaner). Sections: cleaning/anomaly report -> the no-semantic-columns finding -> missingness
-> rating distribution -> playtime & session buckets -> popularity tail -> completion-vs-quality
test -> hidden gems -> metric correlation matrix -> grindiest games -> additions over time
-> data limitations -> takeaways.

### Headline findings (-> design impact)

- **No semantic columns exist** -> enrichment is mandatory before any vibe match. A
  programmatic check for any genre/theme/mood/description column returns `NONE`; this is the
  entire reason the pipeline has a RAWG stage.
- **`completion_pct` is finishability, not quality.** Tested with both Pearson (linear) and
  Spearman (rank): vs rating it's flat (Pearson -0.02 / Spearman +0.10), but vs grind/ratio
  it's strongly monotonic (Spearman -0.85) and vs playtime too (Spearman -0.64). Short,
  low-grind games get finished; good games don't necessarily -> **moved out of the quality
  term** into the session/commitment signal.
- **`gamers` is heavy-tailed** (linear histogram is a spike; `log10` is roughly bell-shaped)
  -> log-scale it so popularity stays a soft prior instead of swamping the blend.
- **`rating` is narrow and survivorship-skewed** (mean ~3.70, range 2.0-4.8 on a curated
  catalog) -> normalize within the observed range, keep it a soft prior.
- **Hidden gems need a quality floor**: ranking by `rating_z - popularity_z` *plus* a rating
  floor (>= 4.1, top quartile) yields 124 genuine candidates -> obscurity alone isn't a gem.
- **`ratio` = grind/difficulty** (correlates with playtime, Spearman +0.51) -> kept out of
  core relevance, reserved for the Insights/flavor surface.
- **Back-catalog is the bulk**: 53.6% of dated titles are >12 months old (latest catalog date
  2022-04-28) -> plenty of older content to reignite, which is the product's goal.
- **Known limitations**: a 2022 snapshot with curated-catalog bias and community/platform-
  specific ratings; missing playtime/rating/date are preserved as unknowns, never imputed.
