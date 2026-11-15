# Third-party notices

Application dependencies are installed separately; this source snapshot does not
vendor their packages. Versions and licenses below were checked against the
installed Python 3.11 verification environment's distribution metadata on
November 15, 2026. Preserve upstream notices if redistributing those packages.

| Direct dependency | Pinned version | Declared license | Primary project |
|---|---|---|---|
| FastAPI | 0.162.7 | MIT | [FastAPI](https://github.com/fastapi/fastapi) |
| Uvicorn | 0.54.0 | BSD-3-Clause | [Uvicorn](https://github.com/encode/uvicorn) |
| Pydantic | 2.14.3 | MIT | [Pydantic](https://github.com/pydantic/pydantic) |
| python-dotenv | 1.2.4 | BSD-3-Clause | [python-dotenv](https://github.com/theskumar/python-dotenv) |
| python-multipart | 0.0.33 | Apache-2.0 | [python-multipart](https://github.com/Kludex/python-multipart) |
| httpx2 | 2.16.0 | BSD-3-Clause | [PyPI distribution](https://pypi.org/project/httpx2/) |
| Playwright (development) | 1.65.2 | Apache-2.0 | [Playwright Python](https://github.com/microsoft/playwright-python) |

The resolved environment additionally includes annotated-doc/types, anyio,
greenlet, h11, httpcore2, idna, opentelemetry-api, pydantic_core, starlette,
truststore, typing_extensions and typing-inspection. Their installed metadata
declares MIT, BSD-3-Clause, Apache-2.0 and/or PSF-2.0 as appropriate; these packages
are not copied into the source handoff. Python itself is separately licensed by
the Python Software Foundation. A browser used for testing has its own license.

Bundled assets: **Geist and Geist Mono**, copyright 2023 Vercel in collaboration
with basement.studio, under SIL Open Font License 1.1. The complete upstream
[OFL notice](app/web/static/fonts/OFL.txt) is retained with the font files.
No remote font, map tile, analytics or media service is needed at runtime.

NASA FIRMS observations and scientific product references are credited in
[SOURCES.md](SOURCES.md) and the case manifest. The project's Apache-2.0 license
does not relicense third-party data, fonts or installed dependencies.
