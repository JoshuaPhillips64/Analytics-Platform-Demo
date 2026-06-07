"""Python EL layer: extract from Alpha Vantage, archive to S3, load raw into RDS.

Golden rule #1: this package only EXTRACTS and LOADS raw data. No cleaning,
joining, or aggregation happens here — all transformation lives in dbt SQL.
"""
