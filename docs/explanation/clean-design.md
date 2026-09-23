# Clean design

When building local registries, `shpc` is fixed to create and use an unversioned `container.yaml`.
In our implementation this is `/apps/local/quay.io/biocontainers/<tool>/container.yaml`.
One limitation is that the version for the built module is not indicated. Although versions are
indicated in the `container.yaml`, the aliases across versions vary and are unreliable.

As we need version provenance for all modules for shelley, [build-design.md] works around this
by first creating the necessary `container.yaml`, then copies this into a version subdirectory 
`/apps/local/quay.io/biocontainers/<tool>/<version>/container.yaml`.

`clean` will reliably remove the versioned subdirectory but the unversioned one will remain,
as we have no way of telling which version it corresponds to. `clean` will remove `/apps/local/quay.io/biocontainers/<tool>/container.yaml`
only if there are no more versioned directories remaining.
