
# Power Pages

**Download:**
```bash
ppx pages download --website-id <GUID> --tables full --out site_dump --host <DV>
```

**Upload:**
```bash
ppx pages upload --website-id <GUID> --src site_dump --host <DV>
```

**Tables:**
- core: websites, webpages, webfiles, contentsnippets, pagetemplates, sitemarkers
- extra: weblinksets, weblinks, webpageaccesscontrolrules, webroles, entitypermissions, redirects
