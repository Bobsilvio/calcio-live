# Calcio Live - Home Assistant Integration

## Supportami / Support Me

Se ti piace il mio lavoro e vuoi che continui nello sviluppo delle card, puoi offrirmi un caffè.\
If you like my work and want me to continue developing the cards, you can buy me a coffee.


[![PayPal](https://img.shields.io/badge/Donate-PayPal-%2300457C?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/donate/?hosted_button_id=Z6KY9V6BBZ4BN)

Non dimenticare di seguirmi sui social:\
Don't forget to follow me on social media:

[![TikTok](https://img.shields.io/badge/Follow_TikTok-%23000000?style=for-the-badge&logo=tiktok&logoColor=white)](https://www.tiktok.com/@silviosmartalexa)

[![Instagram](https://img.shields.io/badge/Follow_Instagram-%23E1306C?style=for-the-badge&logo=instagram&logoColor=white)](https://www.instagram.com/silviosmartalexa)

[![YouTube](https://img.shields.io/badge/Subscribe_YouTube-%23FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@silviosmartalexa)


## Video Guida / Video Guide

[Guarda il video su YouTube](https://www.youtube.com/watch?v=K-FAJmwsGXs)\
[Watch the video on YouTube](https://www.youtube.com/watch?v=K-FAJmwsGXs)

## Descrizione / Description

L'integrazione "Calcio Live" per Home Assistant permette di ottenere informazioni in tempo reale sulle competizioni di calcio, come classifiche, cannonieri e giornate di campionato.\
The "Calcio Live" integration for Home Assistant allows you to get real-time information about football competitions, such as standings, top scorers, and matchdays.
    
<img src="images/campionati.png" alt="HACS" width="800"/>

## Installazione manuale tramite HACS / Manual Installation via HACS

1. ## 📦 Installation simple
[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bobsilvio&repository=calcio-live&category=integration)


2. Vai su Impostazioni > Integrazione > Aggiungi Integrazione e cerca 'Calcio-Live'.\
   Go to Settings > Integration > Add Integration and search for 'Calcio-Live'.

3. Configura l'integrazione tramite l'interfaccia di Home Assistant.\
   Configure the integration via the Home Assistant interface.


### NOTA / NOTE: !!!! NON DIMENTICARE IL PUNTO 7 - LE CARD VANNO INSTALLATE A PARTE COME PUNTO 1 e 2!!!!

!!! DON'T FORGET POINT 7 - THE CARDS MUST BE INSTALLED SEPARATELY AS IN POINTS 1 AND 2 !!!

5. Scegli il campionato da seguire o della tua squadra, è molto intuitivo...\
   Choose the league or team to follow, it is very intuitive...

    <img src="images/integrazione1.png" alt="HACS" width="300"/>
    <img src="images/integrazione2.png" alt="HACS" width="300"/>
    <img src="images/integrazione3.png" alt="HACS" width="300"/>
    <img src="images/integrazione4.png" alt="HACS" width="300"/>

### 7. Per la card, vai su: [https://github.com/Bobsilvio/calcio-live-card](https://github.com/Bobsilvio/calcio-live-card) e segui le istruzioni

### For the card, go to: [https://github.com/Bobsilvio/calcio-live-card](https://github.com/Bobsilvio/calcio-live-card) and follow the instructions

### 8. Per evitare di caricare il sistema di registrazioni sui dati delle partite.
### To avoid overloading the system with match data recordings.

Nel configuration.yaml inserire questo codice:
```yaml
recorder:
  exclude:
    entity_globs:
      - sensor.calciolive_*
  ```

## Note
    Puoi seguire più campionati o più squadre.\
    You can follow multiple leagues or multiple teams.
   
## Automazioni
### Notifica 15 minuti prima dell'inizio della partita
### Notification 15 minutes before match start

<img src="images/inizio_partita.jpg" alt="iniziopartita" width="300"/>

Notifica l'inizio della partita 15 minuti prima usando il sensore `sensor.calciolive_next...`.  
**Nota**: Cambia anche `notify.mobile_app_xxx` con il tuo dispositivo.

```yaml
alias: CalcioLive - Notifica 15 minuti prima della partita Inter
description: Invia una notifica al cellulare 15 minuti prima dell'inizio della partita.
trigger:
  - platform: template
    value_template: >
      {{
      (as_timestamp(strptime(state_attr('sensor.calciolive_next_ita_1_internazionale',
      'matches')[0].date, '%d/%m/%Y %H:%M')) - 900) | timestamp_custom('%Y-%m-%d
      %H:%M') == now().strftime('%Y-%m-%d %H:%M') }}
condition:
  - condition: template
    value_template: >
      {{ state_attr('sensor.calciolive_next_ita_1_internazionale',
      'matches')[0].state == 'pre' }}
action:
  - service: notify.mobile_app_xxx
    data:
      title: CalcioLive - Promemoria Partita
      message: >
        La partita tra {{
        state_attr('sensor.calciolive_next_ita_1_internazionale',
        'matches')[0].home_team }} e {{
        state_attr('sensor.calciolive_next_ita_1_internazionale',
        'matches')[0].away_team }} inizierà tra 15 minuti!
      data:
        image: >
          {{ state_attr('sensor.calciolive_next_ita_1_internazionale', 'team_logo') }}
mode: single
```
---

Notifica Goal con dettagli su minuti e giocatore usando il sensore `sensor.calciolive_next...`.  
**Nota**: Cambia anche `notify.mobile_app_xxx` con il tuo dispositivo.


```yaml
alias: CalcioLive - Notifica Goal Internazionale con Minuti e Giocatore
description: Invia una notifica per ogni gol segnato, inclusi i rigori.
triggers:
  - value_template: >
      {% for event in state_attr('sensor.calciolive_next_ita_1_internazionale',
      'matches')[0].match_details %}
        {% if 'Goal' in event or 'Penalty' in event %}
          true
        {% endif %}
      {% endfor %}
    trigger: template
conditions: []
actions:
  - variables:
      match_details: >-
        {{ state_attr('sensor.calciolive_next_ita_1_internazionale',
        'matches')[0].match_details }}
  - repeat:
      for_each: "{{ match_details }}"
      sequence:
        - variables:
            event: "{{ repeat.item }}"
        - choose:
            - conditions:
                - condition: template
                  value_template: |
                    {{ 'Goal' in event or 'Penalty' in event }}
              sequence:
                - data_template:
                    title: >
                      Partita {{
                      state_attr('sensor.calciolive_next_ita_1_internazionale',
                      'matches')[0].home_team }} vs {{
                      state_attr('sensor.calciolive_next_ita_1_internazionale',
                      'matches')[0].away_team }}
                    message: >
                      {% set tipo = 'Rigore segnato da' if 'Penalty' in event
                      else 'Gol segnato da' %} {% set minuto =
                      event.split("'")[0].split("-")[-1].strip() %} {% set
                      giocatore = event.split("': ")[1].strip() %} ⚽ {{ tipo }}
                      {{ giocatore }} al minuto {{ minuto }}!
                  action: notify.mobile_app_xxx
mode: queued
```

## Informazioni
Questa è la mia prima card e sicuramente c'è tanto lavoro da fare, se vi piace, potete ricambiare seguendomi nei social:
This is my first card, and there is definitely a lot of work to do...

TikTok: @silviosmartalexa
