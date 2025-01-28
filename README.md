# Build the container

```sh
docker -t <container name> .
```

# And run it

```sh
podman run -it -p 8000:8000 -v $(pwd):/app <container name> python gossip.py
```
