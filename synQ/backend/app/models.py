    operating_cost = Column(Float, default=0)  # per hour
    # Configured repair time for this machine, used by the "repair" recovery
    # strategy when a breakdown disruption has no alternative capable machine.
    # Nullable: when unset, the repair strategy falls back to the disruption's
    # own duration_hours parameter, and only as a last resort to a documented
    # default (see simulation.py generate_repair_plan).
    repair_duration_minutes = Column(Float, nullable=True)

    factory = relationship("Factory", back_populates="machines")
