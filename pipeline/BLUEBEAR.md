# Running Ash Watch on BlueBEAR (University of Birmingham)

Run everything from the `pipeline/` folder. Each stage has a check; do not go on until it passes.
Off campus you need the University VPN. If you belong to more than one BEAR project, add
`--account=<project>` to every `sbatch` command.

## 1. Set up (login node, once)

```bash
ssh <username>@bluebear.bham.ac.uk
cd /rds/projects/X/PROJECT                      # your RDS project space, not your home folder
git clone https://github.com/Andrea-S90/Fire-Before-The-Storm.git
cd Fire-Before-The-Storm/pipeline
cp slurm/bluebear.local.sh.example slurm/bluebear.local.sh
module purge; module load bluebear; module avail Python     # pick a Python 3.11 or 3.12 module
nano slurm/bluebear.local.sh                    # set ASHWATCH_DATA, VENV_DIR, BEAR_MODULES
bash scripts/setup_credentials.sh               # Earthdata + CDS logins -> ~/.netrc, ~/.cdsapirc
mkdir -p logs
```

Check: `df -h /rds/projects/X/PROJECT` shows about 100 GB free.

## 2. Smoke test (about 10 minutes)

```bash
sbatch slurm/bluebear_smoke.sbatch
squeue -u $USER                                 # wait until the job has gone
tail -30 logs/smoke_*.log
```

Check: the log ends with `SMOKE TEST PASSED` and lists 9 PNG files. Note the `INTERNET: yes/no` line:
it decides how stage 3 and 4 run. The first job builds the Python environment, so it is the slowest.

If the log says the environment could not be built, the compute node has no internet. Build it on the
login node instead, then resubmit:

```bash
module purge; module load bluebear; source slurm/bluebear_env.sh
```

A job on a different node type builds its own environment the same way, so if compute nodes have no
internet and a later job fails at that point, ask BEAR support how to pin the node type.

## 3. Small real test (2 NISAR files)

`INTERNET: yes`:

```bash
sbatch --export=ALL,NISAR_MAX_FILES=2 slurm/bluebear_download.sbatch
```

`INTERNET: no` (login node; light enough to run there):

```bash
module purge; module load bluebear; source slurm/bluebear_env.sh
python steps/01_download_nisar.py --dry-run
python steps/02_download_ancillary.py dem s2 cci soil osm era5 imerg
python steps/01_download_nisar.py --max-files 2
python steps/inspect_gcov.py "$(ls $ASHWATCH_DATA/raw/nisar/*_PR_GCOV_*.h5 | head -1)"
```

Checks:
- The search reports about 38 products kept (4 passes: 023D, 087A, 095D, 159A).
- `inspect_gcov.py` prints `HHHH` and `HVHV` with medians between about -25 and -5 dB. If it fails, the
  HDF5 layout differs from what `ashwatch/nisar.py` expects: fix that before going on.
- No source is listed under `Failed sources`. For 401/403 errors approve the ASF and GES DISC apps in your
  Earthdata profile; for ERA5 accept the licence on the CDS dataset page.

Then grid the two files:

```bash
sbatch --time=30:0 --export=ALL,STEPS="03 04" slurm/bluebear_process.sbatch
```

Check: `$ASHWATCH_DATA/work/nisar/index.csv` has rows with `HV_valid_pct` well above 0, and
`work/grid/` contains `dem.tif`, `dnbr.tif`, `agb_cci.tif` and `kf.tif`.

## 4. Full download

`INTERNET: yes`: `sbatch slurm/bluebear_download.sbatch`

`INTERNET: no`: `nohup bash scripts/run_downloads.sh > logs/downloads.log 2>&1 &` on the login node, after
sourcing the environment as in stage 3. Login-node processes can be stopped without warning; the download
resumes where it stopped, so just start it again.

Check: `ls $ASHWATCH_DATA/raw/nisar/*.h5 | wc -l` matches `wc -l < $ASHWATCH_DATA/raw/nisar/urls.txt`.

## 5. Full processing

```bash
sbatch slurm/bluebear_process.sbatch
tail -f logs/process_*.log
```

Checks in the log:
- Step 05 reports the fuel model R2 and the severity accuracy and kappa, and the burned area in hectares
  is plausible for the fire.
- Step 10 writes a record for each named town.
- Step 12 ends with `Web export: ... MB` (a few MB).

Re-run part of the chain with `sbatch --export=ALL,STEPS="10 11 12" slurm/bluebear_process.sbatch`.

## 6. Results to the laptop

```bash
# on the laptop, with the VPN on
rsync -av <username>@bluebear.bham.ac.uk:/rds/projects/X/PROJECT/Fire-Before-The-Storm/web/public/data/ web/public/data/
```
