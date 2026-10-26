# test-ports-processor

A test app with **two inputs and two outputs**, for trying workflows that link
one step's outputs to another step's inputs. It does no real work: it reports
where each input's files arrived and copies them on.

## Inputs

| Input | Takes | Found in |
|---|---|---|
| `signals` | CSV files (`text/csv`) | `INPUT_DIR/signals/` if that folder exists, else the `.csv` files at the root of `INPUT_DIR` |
| `events` | JSON files (`application/json`) | `INPUT_DIR/events/` if that folder exists, else the `.json` files at the root of `INPUT_DIR` |

Both inputs have `placement: subfolder`: a workflow that links them gives the
app `INPUT_DIR/signals/` and `INPUT_DIR/events/`, each from its own step or
data source. Without links (or on a compute node from before linked inputs),
the files arrive at the root, where the app finds them by extension.

## Outputs

With two outputs, each is written to its own folder:

| Output | Holds |
|---|---|
| `summary` | `OUTPUT_DIR/summary/report.json`: the whole input tree, the files each input received and where they were found (`signals/`, `root` or `missing`), files no input claims, and whether the step was given LLM access (`llmAccess`; this app doesn't declare `runtime.llm`, so it shouldn't be) |
| `copies` | `OUTPUT_DIR/copies/signals/…` and `OUTPUT_DIR/copies/events/…`: each input's files, copied on |

Linking `copies` to another `test-ports-processor` step gives that step
`INPUT_DIR/signals/` and `INPUT_DIR/events/`, so chains of this app can be
tested too. The run's log shows the same report.

## Parameters

| Parameter | Default | |
|---|---|---|
| `FAIL_IF_MISSING` | `false` | Fail the run when an input has no files, instead of reporting it as missing |

## Runtimes

The image runs either way (`computeTypes: [standard, lambda]` in `app.yml`):

- **standard** (the default): an ECS task. `INPUT_DIR`, `OUTPUT_DIR` and the
  parameters are environment variables, and `main()` runs once.
- **lambda**: a workflow step set to run as a Lambda function. Lambda sets
  `AWS_LAMBDA_RUNTIME_API`, so `processor/entry.py` hands over to the Lambda
  runtime interface client, and `processor/handler.py` takes `inputDir`,
  `outputDir` and the parameters from the payload and runs the same `main()`.
  A failed run raises, so the step fails.

`report.json` says which it ran as (`runtime`: `container` or `lambda`).
Compliant compute nodes refuse lambda steps, and a Lambda step gets no LLM
sidecar.

## Running it locally

```sh
make test   # Python, over sample-input/, printing the report
make run    # the same in Docker
```

As a Lambda function, with the [runtime interface emulator](https://github.com/aws/aws-lambda-runtime-interface-emulator)
(`aws-lambda-rie` for your machine's architecture) in the image's place:

```sh
docker build -t test-ports-processor .
docker run --rm -p 9000:8080 -v "$PWD/sample-input:/in:ro" -v "$PWD/aws-lambda-rie:/rie:ro" \
  --entrypoint /rie test-ports-processor python3 -m processor.entry
curl -XPOST localhost:9000/2015-03-31/functions/function/invocations \
  -d '{"inputDir": "/in", "outputDir": "/tmp/out", "FAIL_IF_MISSING": "false"}'
```

`sample-input/` has one file for each input, at the root.
