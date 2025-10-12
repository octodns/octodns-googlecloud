## 1.1.0 - 2025-10-11

Minor:
* Add `private` param to allow filtering public/private zones - [#66](https://github.com/None/pull/66)
* Remove protobuf version pinning as google-cloud libs are broken with it

Patch:
* Fix multiple values records updates and deletions when their values aren't sorted on Google Cloud DNS side - [#70](https://github.com/None/pull/70)
* Fixing issue PtrRecord has no setter for property value - [#65](https://github.com/None/pull/65)
* Use new [changelet](https://github.com/octodns/changelet) tooling - [#62](https://github.com/None/pull/62)

## v1.0.0 - 2025-05-04 - Long overdue 1.0

* Support for `DS` record types
* Address pending octoDNS 2.x deprecations, require minimum of 1.5.x

## v0.0.3 - 2023-02-08 - AKA

* Support for `ALIAS` record types

## v0.0.2 - 2022-10-29

* Enable support for root level NS records (`SUPPORTS_ROOT_NS=true`)

## v0.0.1 - 2022-01-11 - Moving

#### Nothworthy Changes

* Initial extraction of GoogleCloudProvider from octoDNS core

#### Stuff

Nothing
