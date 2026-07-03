---
title: "{{subject}}"
from: "{{from}}"
to: "{{to}}"
cc: "{{cc}}"
date: {{date_iso}}
message_id: "{{message_id}}"
folder: "{{folder}}"
source: email
tags: [email]
---

# {{subject}}

**From:** {{from}}
**To:** {{to}}
**Date:** {{date_human}}
{{attachments_block}}
{{body}}
