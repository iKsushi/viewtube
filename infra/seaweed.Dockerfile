FROM chrislusf/seaweedfs:4.52
USER root
RUN mkdir -p /data/filer /data/volumes /data/master && chown -R 10001:10001 /data
COPY filer.toml /etc/seaweedfs/filer.toml
USER 10001:10001
WORKDIR /data
ENTRYPOINT ["weed"]
CMD ["server", "-ip=storage", "-ip.bind=0.0.0.0", "-dir=/data/volumes", "-master.dir=/data/master", "-master.telemetry=false", "-master.volumeSizeLimitMB=512", "-volume.max=0", "-volume.minFreeSpace=1GiB", "-filer", "-filer.exposeDirectoryData=false", "-s3", "-s3.port=8333", "-s3.port.iceberg=0", "-s3.port.lance=0", "-s3.config=/etc/seaweedfs/s3.json"]
