"""Per-process identity baggage on the aura-otel contract keys."""

import os

from opentelemetry.baggage import set_baggage
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.context import get_current
from opentelemetry.propagators.textmap import default_setter

from pulse_otel.consts import (
	APP_NAME_PLACEHOLDER,
	BAGGAGE_ORG,
	BAGGAGE_PROJECT,
	BAGGAGE_NOVA_ID,
	BAGGAGE_NOVA_TYPE,
	BAGGAGE_NOVA_NAME,
)


def _process_identity_baggage():
	"""Fixed per-process identity (org/project + the agent's nova app) on the
	aura-otel contract keys, from the notebook-server env. Per-request dims
	(session/domain) are not here; the caller seeds those. Empty/placeholder
	values are dropped."""
	name = os.getenv("SINGLESTOREDB_APP_NAME", "")
	identity = {
		BAGGAGE_ORG: os.getenv("SINGLESTOREDB_ORGANIZATION", ""),
		BAGGAGE_PROJECT: os.getenv("SINGLESTOREDB_PROJECT", ""),
		BAGGAGE_NOVA_ID: os.getenv("SINGLESTOREDB_APP_ID", ""),
		BAGGAGE_NOVA_TYPE: os.getenv("SINGLESTOREDB_APP_TYPE", ""),
		BAGGAGE_NOVA_NAME: "" if name == APP_NAME_PLACEHOLDER else name,
	}
	return {k: v for k, v in identity.items() if v}


def _apply_identity_baggage(context, identity):
	ctx = context if context is not None else get_current()
	for key, value in identity.items():
		ctx = set_baggage(key, value, context=ctx)
	return ctx


def seed_identity_baggage(context=None):
	"""Seed this process's identity (org/project/nova, on the aura-otel contract
	keys) onto *context* and return it. The global propagator installed by Pulse
	already injects these on every outbound call; call this only to seed a context
	explicitly. Per-request dims (session/domain) are the caller's job."""
	return _apply_identity_baggage(context, _process_identity_baggage())


class _IdentityBaggagePropagator(W3CBaggagePropagator):
	"""W3C baggage propagator that also injects the per-process identity from
	_process_identity_baggage() on inject, so downstream Go services stamp
	org/project/nova from baggage. Non-identity inbound baggage passes through."""

	def __init__(self):
		super().__init__()
		self._identity = _process_identity_baggage()

	def inject(self, carrier, context=None, setter=default_setter):
		ctx = _apply_identity_baggage(context, self._identity)
		super().inject(carrier, context=ctx, setter=setter)
