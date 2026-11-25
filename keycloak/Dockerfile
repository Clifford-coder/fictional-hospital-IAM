# Part 2, Phase 1: optimized Keycloak image.
# The base image is pinned by digest. Keep it identical to KEYCLOAK_IMAGE in versions.env.

# ---- Stage 1: build. Fixes the build-time options and bakes them into the server. ----
FROM quay.io/keycloak/keycloak:26.7.4@sha256:82a77884f3af238beab1e7afd63b5f530e1b5c0590bd7aa60b40a40463e29b2c AS builder

# Build-time options only. The hostname, database address, credentials and every
# other runtime setting stay out of the image and are supplied when it runs.
ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=true
RUN /opt/keycloak/bin/kc.sh build

# ---- Stage 2: the image that runs. ----
FROM quay.io/keycloak/keycloak:26.7.4@sha256:82a77884f3af238beab1e7afd63b5f530e1b5c0590bd7aa60b40a40463e29b2c

# The optimized server from stage 1. Owner 1000 is Keycloak's own non-root user; group 0
# keeps the files usable if the platform assigns a different user ID.
COPY --from=builder --chown=1000:0 /opt/keycloak/ /opt/keycloak/

# The realm: roles, groups and their role mappings, clients, the authentication flow,
# policies and event settings. It contains no users and no passwords; client secrets are
# ${...} placeholders that Keycloak fills from environment variables at import.
COPY --chown=1000:0 realm/hospital-realm.json /opt/keycloak/data/import/hospital-realm.json

ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]

# start --optimized  : skip the build step at boot; the server starts the same way every time.
# --import-realm     : import the realm only if it does not exist yet (it is ignored afterwards).
# --spi-...=info     : also log successful sign-ins (hidden at the default level); a runtime option.
CMD ["start", "--optimized", "--import-realm", "--spi-events-listener--jboss-logging--success-level=info"]
