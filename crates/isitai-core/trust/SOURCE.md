# C2PA trust lists

Unmodified copies of three trust lists. Two are the official C2PA trust lists:
`C2PA-TRUST-LIST.pem` holds the roots of manifest signers, `C2PA-TSA-TRUST-LIST.pem` the
roots of time-stamp authorities. `C2PA-INTERIM-TRUST-LIST.pem` is the interim trust list
that the Content Authenticity Initiative kept before the official lists existed: it holds
roots of manifest signers and of time-stamp authorities, and upstream has frozen it. Do
not edit them by hand: run `scripts/update_trust_list.sh`.

Fetched: 2026-11-12

## `C2PA-TRUST-LIST.pem`

| | |
|---|---|
| Upstream repository | https://github.com/c2pa-org/conformance-public |
| Path | `trust-list/C2PA-TRUST-LIST.pem` |
| Commit | `64b3f9c8ebb95d2b73557aea25172d694db67c1e` (2026-11-04T17:09:28Z) |
| Certificates | 33 |
| SHA-256 | `148c1c167e98dc909a0d5793d2feee1022aa60fef5c83a0d6b08f67f4446bc37` |
| Licence | CC-BY-4.0, https://creativecommons.org/licenses/by/4.0/ |

## `C2PA-TSA-TRUST-LIST.pem`

| | |
|---|---|
| Upstream repository | https://github.com/c2pa-org/conformance-public |
| Path | `trust-list/C2PA-TSA-TRUST-LIST.pem` |
| Commit | `64b3f9c8ebb95d2b73557aea25172d694db67c1e` (2026-11-04T17:09:28Z) |
| Certificates | 24 |
| SHA-256 | `eca8347ee71e31d226e00c85b15aca356116fefe6c26ed8c0ee1f954115b1990` |
| Licence | CC-BY-4.0, https://creativecommons.org/licenses/by/4.0/ |

## `C2PA-INTERIM-TRUST-LIST.pem`

| | |
|---|---|
| Upstream repository | https://github.com/contentauth/verify-site |
| Path | `static/trust/anchors.pem` |
| Commit | `c2bf16d559ea4a70cb20d44cd1caee6c3bac9ec0` (2026-01-08T22:47:56Z) |
| Certificates | 27 PEM blocks, 26 different |
| SHA-256 | `db57e50b9bd4e4c786cbb91f38fd85e2af6a9d5412438a8cddcc42688df07ae5` |
| Licence | none stated for this file; see the note below |

Attribution: "C2PA Trust List" and "C2PA TSA Trust List", by the Coalition for Content
Provenance and Authenticity (C2PA), from `c2pa-org/conformance-public`.

The interim trust list comes from the verify site of the Content Authenticity Initiative
(`contentauth/verify-site`). Its licence, as found on 2026-11-12: the file and its directory
carry no licence or copyright notice; the repository holds `LICENSE-APACHE`
("Copyright 2020 Adobe") and its README places the project under the Apache License 2.0
(https://www.apache.org/licenses/LICENSE-2.0), while its `package.json` says
`"license": "UNLICENSED"`. The list holds public root certificates of third parties.
