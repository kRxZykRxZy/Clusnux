import docker
from docker.errors import NotFound, ImageNotFound, APIError

client = docker.from_env()

def run_container(image_name, container_name, command=None):
    """
    Runs a container by name.
    - Pulls the image if it doesn't exist locally.
    - Streams logs in real-time.
    """
    try:
        # Check if the container already exists
        container = client.containers.get(container_name)
        print(f"Container '{container_name}' already exists. Starting it...")
        container.start()
    except NotFound:
        # Container doesn't exist, pull image if needed
        try:
            print(f"Pulling image '{image_name}' if it doesn't exist...")
            client.images.pull(image_name)
        except ImageNotFound:
            print(f"Image '{image_name}' not found on registry.")
            return
        except APIError as e:
            print(f"Error pulling image: {e}")
            return

        # Run the container
        print(f"Running new container '{container_name}'...")
        container = client.containers.run(
            image_name,
            command=command,
            name=container_name,
            detach=True,
            stdout=True,
            stderr=True,
            tty=True
        )

    # Stream logs
    print(f"Streaming logs for container '{container_name}'...")
    for log in container.logs(stream=True):
        print(log.decode().strip())
    
    return container
