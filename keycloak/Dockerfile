FROM quay.io/keycloak/keycloak:26.7.4

# Turns on the health endpoints.
ENV KC_HEALTH_ENABLED=true

# Realm definition (roles, groups, seeded users), placed where Keycloak looks for imports
COPY realm/hospital-realm.json /opt/keycloak/data/import/hospital-realm.json

# --import-realm imports it on first start (skipped if the realm already exists)
CMD ["start-dev", "--import-realm"]