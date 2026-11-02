# BRAINY — COMPLETE SECURITY TEST MATRIX

**Execution Date:** November 2026  
**Environment:** Isolated Security Test Environment (`tests/test_security_hardening.py`, `tests/test_encryption_aead.py`, unit test discovery suite)  
**Total Test Cases:** 244  
**Passed:** 244  
**Failed:** 0  
**Blocked:** 0  
**Skipped:** 0  
**Test Suite Execution Time:** 3.866 seconds  

---

## 1. Security Control Verification Matrix

| Test ID | Security Domain | Target Component / Threat | Verification Method & Test Name | Expected Outcome | Actual Outcome | Status |
|---|---|---|---|---|---|---|
| **SEC-T01** | CSRF Defense | Cross-Site POST with forged Origin | `test_csrf_cookie_post_rejected_with_untrusted_origin` | Reject with HTTP 403 `CSRF_ORIGIN_REJECTED` | HTTP 403 returned | **PASS** |
| **SEC-T02** | CSRF Defense | Cross-Site navigation (`Sec-Fetch-Site: cross-site`) | `test_csrf_cookie_post_rejected_with_sec_fetch_site_cross_site` | Reject with HTTP 403 | HTTP 403 returned | **PASS** |
| **SEC-T03** | CSRF Defense | Legitimate Origin in `DEFAULT_ALLOWED_ORIGINS` | `test_csrf_cookie_post_allowed_with_trusted_origin` | Permit request (HTTP 200) | HTTP 200 returned | **PASS** |
| **SEC-T04** | CSRF Defense | Same-origin Referer header | `test_csrf_cookie_post_allowed_with_trusted_referer` | Permit request (HTTP 200) | HTTP 200 returned | **PASS** |
| **SEC-T05** | Auth / Bearer | Lowercase `bearer <token>` authorization | `test_bearer_token_case_insensitive_lowercase` | Authenticate request successfully | Authenticated | **PASS** |
| **SEC-T06** | Auth / Bearer | Mixed-case `BeArEr <token>` authorization | `test_bearer_token_case_insensitive_mixed_case` | Authenticate request successfully | Authenticated | **PASS** |
| **SEC-T07** | Auth / Bearer | Malformed Authorization header | `test_malformed_auth_header_rejected` | Reject with HTTP 401 | HTTP 401 returned | **PASS** |
| **SEC-T08** | RBAC / Admin | Student token accessing `/api/admin/users` | `test_admin_required_blocks_student_token` | Reject with HTTP 403 Forbidden | HTTP 403 returned | **PASS** |
| **SEC-T09** | RBAC / Admin | Unauthenticated request to `/api/admin/users` | `test_admin_required_blocks_unauthenticated_request` | Reject with HTTP 401 Unauthorized | HTTP 401 returned | **PASS** |
| **SEC-T10** | RBAC / Admin | Verified Admin token accessing `/api/admin/users` | `test_admin_required_allows_verified_admin_token` | Permit request (HTTP 200) | HTTP 200 returned | **PASS** |
| **SEC-T11** | Model Security | Ingestion of unwhitelisted AI model ID | `test_unregistered_model_raises_value_error` | Reject model with `ValueError` | ValueError raised | **PASS** |
| **SEC-T12** | Model Security | Ingestion of valid registered model ID | `test_registered_model_passes_validation` | Validation passes | Model validated | **PASS** |
| **SEC-T13** | SSRF Defense | Cloud metadata IP (`http://169.254.169.254/latest/meta-data`) | `test_ssrf_blocks_metadata_ip` | Discard URL (return empty string) | Discarded | **PASS** |
| **SEC-T14** | SSRF Defense | Loopback IPv4 (`http://127.0.0.1:8000/admin`) | `test_ssrf_blocks_loopback_ipv4` | Discard URL (return empty string) | Discarded | **PASS** |
| **SEC-T15** | SSRF Defense | Loopback IPv6 (`http://[::1]:5000/api`) | `test_ssrf_blocks_loopback_ipv6` | Discard URL (return empty string) | Discarded | **PASS** |
| **SEC-T16** | SSRF Defense | Private Class A IP (`http://10.0.0.1:8080/internal`) | `test_ssrf_blocks_private_class_a` | Discard URL (return empty string) | Discarded | **PASS** |
| **SEC-T17** | SSRF Defense | Private Class B IP (`http://172.16.5.10/status`) | `test_ssrf_blocks_private_class_b` | Discard URL (return empty string) | Discarded | **PASS** |
| **SEC-T18** | SSRF Defense | Private Class C IP (`http://192.168.1.1/router`) | `test_ssrf_blocks_private_class_c` | Discard URL (return empty string) | Discarded | **PASS** |
| **SEC-T19** | SSRF Defense | Cloud metadata hostname (`http://metadata.google.internal/`) | `test_ssrf_blocks_metadata_hostnames` | Discard URL (return empty string) | Discarded | **PASS** |
| **SEC-T20** | SSRF Defense | Non-standard port (`https://example.com:22/`) | `test_ssrf_blocks_non_standard_ports` | Discard URL (return empty string) | Discarded | **PASS** |
| **SEC-T21** | SSRF Defense | Embedded userinfo credentials (`https://admin:pass@example.com/`) | `test_ssrf_blocks_userinfo_credentials` | Discard URL (return empty string) | Discarded | **PASS** |
| **SEC-T22** | SSRF Defense | Legitimate public HTTPS URL (`https://en.wikipedia.org/wiki/Physics`) | `test_ssrf_allows_public_https_url` | Preserve URL | Preserved | **PASS** |
| **SEC-T23** | AI Prompt Safety | Untrusted search grounding prompt injection attempt | `test_search_grounding_fence_and_prompt_safety` | Wrap inside boundary fence with safety directive | Boundary fenced | **PASS** |
| **SEC-T24** | Info Disclosure | Internal 500 error exception containing SQL query string | `test_500_error_response_contains_no_internal_details` | Return generic message and request ID; zero internal leak | Generic JSON | **PASS** |
| **SEC-T25** | Security Headers | Verification of `nosniff`, `SAMEORIGIN`, `strict-origin` | `test_security_headers_present_on_all_responses` | All headers present on HTTP response | Headers present | **PASS** |
| **SEC-T26** | Security Headers | HSTS header on HTTPS forwarded requests | `test_hsts_header_present_on_https_requests` | `Strict-Transport-Security: max-age=31536000` | Header present | **PASS** |
| **SEC-T27** | Security Headers | Cache-Control: no-store on sensitive API routes | `test_cache_control_no_store_on_api_endpoints` | `Cache-Control: no-store, no-cache, must-revalidate` | Header present | **PASS** |
| **SEC-T28** | Session Invalidation | Bearer token revocation upon `/api/auth/logout` | `test_token_revocation_on_logout` | Invalidate token; return 401 on subsequent calls | Token rejected | **PASS** |
| **SEC-T29** | Session Invalidation | User-wide token revocation threshold | `test_user_wide_revocation_invalidates_earlier_tokens` | All tokens issued prior to revocation threshold rejected | Token rejected | **PASS** |
| **SEC-T30** | Mass Assignment | Injected keys (`role`, `is_admin`, `quota`) in `/api/user/preferences` | `test_preference_mass_assignment_disallowed_keys_ignored` | Filter out disallowed keys; retain only whitelisted keys | Keys filtered | **PASS** |
| **SEC-T31** | Input Validation | Non-dictionary body payload in `/api/user/preferences` | `test_preference_rejects_non_dict_body` | Reject with HTTP 400 | HTTP 400 returned | **PASS** |
| **SEC-T32** | BFLA Protection | Regular student requesting `/api/admin/ai-health` | `test_student_user_forbidden_from_admin_ai_health` | Reject with HTTP 403 Forbidden | HTTP 403 returned | **PASS** |
| **SEC-T33** | CSP Hardening | Directives `object-src 'none'` and `base-uri 'self'` | `test_csp_includes_object_src_none_and_base_uri_self` | Directives present in `Content-Security-Policy` | Directives verified | **PASS** |
| **SEC-T34** | Encryption AEAD | AES-256-GCM memory encryption and decryption | `test_encryption_aead.py` | Encrypt with `enc_v2_`, authenticate tag, decrypt cleanly | Decrypted cleanly | **PASS** |
| **SEC-T35** | Encryption AEAD | Tampered ciphertext detection | `test_encryption_aead.py` | Tampered byte causes decryption failure | Verification failed | **PASS** |
| **SEC-T36** | PDF Security | Path traversal attempt in upload filename (`../../etc/passwd.pdf`) | `tests/test_pdf_service.py` | Strip path traversal; isolate to user folder | Clean basename | **PASS** |
| **SEC-T37** | PDF Security | File header magic bytes verification (non-PDF rejected) | `tests/test_pdf_service.py` | Reject with `PDFValidationError` | Rejected | **PASS** |
| **SEC-T38** | PDF Security | Cross-user document retrieval (IDOR test) | `tests/test_pdf_service.py` | Reject with `PDFSecurityError` (HTTP 403) | HTTP 403 returned | **PASS** |
| **SEC-T39** | PDF Security | 5-day retention cleanup of expired binary documents | `tests/test_pdf_service.py` | Delete PDF binary; retain generated notes and progress | Expired cleaned | **PASS** |
| **SEC-T40** | Math Safety | Disallowed functions (`__import__`, `eval`, `exec`) in math engine | `tests/test_maths.py` | Reject expression via AST allowlist; zero code exec | Rejected | **PASS** |

---

## 2. Regression Test Summary

In addition to the 40 targeted security controls listed above, the complete 244-test regression suite was executed across:
- `test_ai_router.py` (AI model selection, prompt budget allocation, latency failover)
- `test_pdf_service.py` (PDF ingestion, PyMuPDF native extraction, Tesseract OCR fallback, quiz generation, notes assistant)
- `test_study_bot.py` (Chat sessions, message persistence, quota windows, user profiles)
- `test_encryption_aead.py` (AES-256-GCM authenticated memory encryption)
- `test_security_hardening.py` (CSRF, Bearer auth, admin RBAC, SSRF, prompt injection, error sanitization, session revocation, mass assignment, CSP)

**Final Test Result:** All 244 tests passed with zero errors or regressions.
