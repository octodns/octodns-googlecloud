## Google Cloud DNS provider for octoDNS

An [octoDNS](https://github.com/octodns/octodns/) provider that targets [Google Cloud DNS](https://cloud.google.com/dns).

### Installation

#### Command line

```
pip install octodns_googlecloud
```

#### requirements.txt/setup.py

Pinning specific versions or SHAs is recommended to avoid unplanned upgrades.

##### Versions

```
# Start with the latest versions and don't just copy what's here
octodns==0.9.14
octodns_googlecloud==0.0.1
```

##### SHAs

```
# Start with the latest/specific versions and don't just copy what's here
-e git+https://git@github.com/octodns/octodns.git@9da19749e28f68407a1c246dfdf65663cdc1c422#egg=octodns
-e git+https://git@github.com/octodns/octodns-googlecloud.git@ec9661f8b335241ae4746eea467a8509205e6a30#egg=octodns_googlecloud
```

### Configuration

```yaml
providers:
  googlecloud:
    class: octodns_googlecloud.GoogleCloudProvider
    # Credentials file for a service_account or other account can be
    # specified with the GOOGLE_APPLICATION_CREDENTIALS environment
    # variable. (https://console.cloud.google.com/apis/credentials)
    #
    # The project to work on (not required)
    # project: foobar
    #
    # The File with the google credentials (not required). If used, the
    # "project" parameter needs to be set, else it will fall back to the
    #  "default credentials"
    # credentials_file: ~/google_cloud_credentials_file.json
    #
    # GoogleCloudProvider submits changes in batches. The default batch size
    # is 1000, which is also roughly the maximum size that google supports.
    # If your plan & apply makes more than batch_size changes they will be
    # broken up into smaller sets of at most that size.
    # batch_size: 1000
```

### Support Information

#### Records

GoogleCloudProvider supports A, AAAA, CAA, CNAME, MX, NAPTR, NS, PTR, SPF, SRV, and TXT

#### Dynamic

GoogleCloudProvider does not support dynamic records.

### Development

See the [/script/](/script/) directory for some tools to help with the development process. They generally follow the [Script to rule them all](https://github.com/github/scripts-to-rule-them-all) pattern. Most useful is `./script/bootstrap` which will create a venv and install both the runtime and development related requirements. It will also hook up a pre-commit hook that covers most of what's run by CI.
