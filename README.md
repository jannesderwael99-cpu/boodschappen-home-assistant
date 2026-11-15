# Boodschappen voor Home Assistant

Koppel je **Boodschappen**-lijst (de Android-app met kassatickets, prijsvergelijking en gerechten) met je eigen Home Assistant.

- 🛒 **Takenlijst `todo.boodschappen`**: je gedeelde boodschappenlijst, live in Home Assistant. Toevoegen, aanpassen, afvinken en verwijderen kan in de app én in Home Assistant.
- 🗣️ **Assist**: "Zet melk op Boodschappen" werkt meteen met de spraakassistent van Home Assistant.
- 🔢 **Sensor "Te halen"**: hoeveel er nog op de lijst staat, met de items als attribuut (voor dashboards en meldingen).
- ⚙️ **Service `boodschappen.add_items`**: meerdere producten tegelijk toevoegen, met hoeveelheid en notitie (bv. vanuit een automatisering).

**Veilig:** Home Assistant maakt zelf verbinding met de Boodschappen-server, met je eigen account. De app of de server kan je Home Assistant nooit bereiken. Je wachtwoord wordt niet bewaard: Home Assistant krijgt een eigen sleutel.

## Installeren via HACS

1. Open **HACS** in Home Assistant → menu (⋮) → **Aangepaste repositories**.
2. Plak `https://github.com/jannesderwael99-cpu/boodschappen-home-assistant`, kies type **Integratie** en klik **Toevoegen**.
3. Zoek **Boodschappen** in HACS en klik **Downloaden**. Herstart Home Assistant.
4. Ga naar **Instellingen → Apparaten & diensten → Integratie toevoegen → Boodschappen**.
5. Vul het adres van je Boodschappen-server en het wachtwoord van de app in. Klaar.

<details><summary>Zonder HACS</summary>

Kopieer de map `custom_components/boodschappen` naar de map `config/custom_components/` van je Home Assistant en herstart.
</details>

## Hoe het werkt

| In de app | In Home Assistant |
|---|---|
| Gehakt · 500 g | `Gehakt (500 g)` |
| Notitie "Voor lasagne (4 p.)" | beschrijving van het item |
| Afgevinkt | voltooid (blijft 24 uur zichtbaar) |

Zet je in Home Assistant `Tomaten (1 kg)` op de lijst, dan verschijnt in de app *Tomaten* met hoeveelheid *1 kg*.

Home Assistant haalt de lijst standaard elke minuut op; dat kan je aanpassen via **Configureren** bij de integratie. Wijzigingen vanuit Home Assistant staan meteen in de app.

### Voorbeelden

Producten toevoegen vanuit een automatisering:

```yaml
action: boodschappen.add_items
data:
  items:
    - "Melk (2 l)"
    - name: Gehakt
      quantity: 500 g
  note: "Voor lasagne (4 p.)"
```

Melding als je thuiskomt en er nog iets op de lijst staat:

```yaml
triggers:
  - trigger: zone
    entity_id: person.jij
    zone: zone.home
    event: leave
conditions:
  - condition: numeric_state
    entity_id: sensor.boodschappen_te_halen
    above: 0
actions:
  - action: notify.notify
    data:
      message: "Nog te halen: {{ state_attr('sensor.boodschappen_te_halen', 'items') | join(', ') }}"
```
