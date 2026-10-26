# test-ports-processor

A test app with **two inputs and two outputs**, for trying workflows that link
one step's outputs to another step's inputs. It does no real work: it reports
where each input's files arrived and copies them on.

## Inputs

| Input | Takes | Found in |
|---|---|---|
| `signals` | CSV files (`text/csv`) | `INPUT_DIR/signals/` if that folder exists, else the `.csv` files at the root of `INPUT_DIR` |
| `events` | JSON files (`application/json`) | `INPUT_DIR/events/` if that folder exists, else the `.json` files at the root of `INPUT_DIR` |

The two inputs take different media types, so they can share the root of
`INPUT_DIR`. When a workflow places an input in its own folder
(`placement: subfolder`), the app finds it there.

## Outputs

With two outputs, each is written to its own folder:

| Output | Holds |
|---|---|
| `summary` | `OUTPUT_DIR/summary/report.json`: the whole input tree, the files each input received and where they were found (`signals/`, `root` or `missing`), and files no input claims |
| `copies` | `OUTPUT_DIR/copies/signals/…` and `OUTPUT_DIR/copies/events/…`: each input's files, copied on |

Linking `copies` to another `test-ports-processor` step gives that step
`INPUT_DIR/signals/` and `INPUT_DIR/events/`, so chains of this app can be
tested too. The run's log shows the same report.

## Parameters

| Parameter | Default | |
|---|---|---|
| `FAIL_IF_MISSING` | `false` | Fail the run when an input has no files, instead of reporting it as missing |

## Running it locally

```sh
make test   # Python, over sample-input/, printing the report
make run    # the same in Docker
```

`sample-input/` has one file for each input, at the root.
