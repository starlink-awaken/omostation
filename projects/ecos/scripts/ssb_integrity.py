from ecos.core.ssb_auth import verify


def main():
    result = verify(limit=50)
    return 0 if result.get("mismatch", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
