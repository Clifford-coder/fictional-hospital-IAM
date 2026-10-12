FROM quay.io/keycloak/keycloak:26.7.4

# Turns on the health endpoints.
ENV KC_HEALTH_ENABLED=true

# Realm definition (roles, groups, seeded users), placed where Keycloak looks for imports
COPY realm/hospital-realm.json /opt/keycloak/data/import/hospital-realm.json

# Dev mode with two additions:
#   --import-realm: import the realm on first start (skipped if it already exists)
#   --spi-events-listener--jboss-logging--success-level=info: also log successful
#     events (logins, logouts), which are hidden at the default debug level
CMD ["start-dev", "--import-realm", "--spi-events-listener--jboss-logging--success-level=info"]