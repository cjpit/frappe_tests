## tests

Usage: in frappe-bench directory, 
```
bench get-app https://github.com/cjpit/frappe_tests
./env/pip install pytest
# create a empty test site
bench new-site test.local
cd sites
export site=test.local && ../env/bin/pytest ../apps/tests

```

#### License

MIT
