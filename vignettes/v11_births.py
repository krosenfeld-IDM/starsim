"""
Vignette 11: Births and pregnancy
"""
import stisim as ss

# Default behavior uses a static population (no births or deaths)
sim = ss.Sim(modules=ss.syphylis())

# EXAMPLES WITH BIRTHS AND PREGNANCY
# Birth outcomes to capture - DARCY / RICH / WHI to contribute:
#   - miscarriages
#   - stillborns
#   - neonatal deaths
#   - MTCT:
#       - chlamydia: during birth
#       - gonorrhea: during birth
#       - HIV: during pregnancy and breastfeeding
#       - syphilis: during pregnancy
#
# Others to consider but possibly not capture
#   - low birth weight
#   - premature births
#   - deformities (may appear weeks-years after birth)

# Note, when implementing this, we will need to generate more pregnancies to offset the ones
# that are lost due to STIs.
# E.g., suppose the crude birth rate for 25yo women is 60 live births per 1000 women.
# We create 60 pregnancies and calculate that 10 of these will be stillborns or miscarriages.
# We will then need to add in 10 extra pregnancies/births.
# TBC:
#   - when should we do this adjustment? Presumably after interventions?
#   - we would have a check at time t to see whether we had enough births at time t
#   - should we just generate the 10 additional births ex nihilo, i.e. not from pregnancies??
#   - it will be difficult to get coverage of interventions right, but the data may not be robust enough to know this.


# Example: adding birth outcomes - simple
# The simplest way to do this is to directly specifying a birth rate, as in this example.
# By default, this would not be age-specific, i.e. in this example, we would generate
# 28 new agents each year per 1000 existing agents, and then we'd randomly assign these
# pregnancies to women aged 15-49.
pars = dict(
    birth_rate=0.028,  # Crude birth rate = 28/1000 people
    death_rate=0.008,  # Crude death rate = 8/1000 people
)
sim = ss.Sim(pars=pars, modules=ss.syphilis())
sim.run()  # print something saying that the pregnancy module and the maternal network are being added

sim.results.syphilis.stillborns.plot()  # Plot a time series of stillborns
# Q: for birth outcomes, should these be added directly to the sim as well i.e. sim.results.stillborns?

# Example: adding birth outcomes - realistic
# If people specify a location, we should load default demographic data for that place:
#   1. a time series of death rates by age and sex,
#   2. a time series of age-specific birth rates
# We use the latter to generate pregnancies in agents.
sim = ss.Sim(location='rwanda', modules=ss.syphilis())

# Implementing this:
# Should we upload individual country data files? Do we need to do this?
