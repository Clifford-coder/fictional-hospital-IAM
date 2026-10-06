FROM quay.io/keycloak/keycloak:26.7.4

# Turns on the health endpoints.
ENV KC_HEALTH_ENABLED=true

COPY realm/hospital-realm.json /opt/keycloak/data/import/hospital-realm.json

CMD ["start-dev", "--import-realm"]