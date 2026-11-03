# Core scripts

Contient les scripts destinés à tourner sur le raspberry.

Le chemin vers ces scripts doit être indiqué par la variable d'environnement **SCRIPTS_PATH**.

## gpio.py

Script ayant plusieurs fonctions :

- monitoring du bouton d'extinction : Retourne 255 (-1) lors de l'appui du bouton
- affichage sur l'écran OLED 128x32 (SSD1306, I2C `0x3C`, via la librairie **luma.oled**) :
	- `BAT` : pourcentage de batterie donné par la jauge, suivi de `LOW` s'il est inférieur à `LOW_BATTERY_PERCENT`
	- `SD` : taux d'occupation de la carte SD et espace libre, ou `FULL` si l'espace libre est inférieur à `LOW_STORAGE_TRESHOLD`
	- `REC` : `ON` si un processus `ros2 bag record` est en cours, `OFF` sinon
	- un point clignotant en haut à droite indique que le script tourne
	- lors d'un arrêt (bouton ou batterie vide), un message est affiché jusqu'à la coupure de l'alimentation
- monitoring de la batterie : mesure la tension et l'état de charge toutes les 10s. Retourne 254 (-2) si la tension est inférieure à la tension minimale.
- monitoring de l'espace de stockage restant (toutes les 30s) : un espace insuffisant est signalé sur l'écran mais ne provoque pas l'arrêt de raspberry

Si l'écran n'est pas détecté au démarrage, le script continue de fonctionner sans affichage.

### Valeurs par défaut (paramètrables dans gpio.py)

- **BTN_RST_GPIO=20** : gpio pin auquel est connecté le bouton d'arrêt.
- **OLED_I2C_PORT=1** / **OLED_I2C_ADDRESS=0x3C** : bus et adresse I2C de l'écran
- **BUTTON_SHUTDOWN=255** : valeur de retour (alias code d'erreur) pour un appui sur le bouton. **NE PAS MODIFIER (à moins de corriger le script gpio.sh en conséquence)**
- **BUTTON_SHUTDOWN=254** : valeur de retour (alias code d'erreur) pour une batterie faible (voltage trop faible). **NE PAS MODIFIER (à moins de corriger le script gpio.sh en conséquence)**
- **NBR_CELLS=2** : nombre d'accus dans la batterie
- **CHARGE_VOLTAGE=4.2** : tension de charge d'un accu, cette valeur * le nombre d'accus définit la tension maximale de la batterie (lorsqu'elle est à 100%)
- **MIN_VOLTAGE=3** : tension minimale d'un accu.

**Ex:** Avec nbr_cells=2 et min_voltage=3, la tension de seuil à partir de laquelle le raspberry est éteint est de 2*3=6V

## gpio.sh

Script lancé au démarrage par [**gpiod.service**](../setup/systemd/README#gpiodservice).

Service ayant plusieurs fonctions :

- log des heures de démarrage et d'extinction du raspberry dans *****$CYCLOSAFE_LOGS**/cyclosafe.log*** + cause de l'extinction (batterie ou bouton)
- lance le script python (**gpio.py**)
- teste la valeur de retour du script et déclenche l'arrêt du raspbbery ssi le code d'erreur correspond à un appui sur le bouton ou à un voltage trop faible sur la batterie.
- déclenche l'arrêt du raspberry via ***sudo systemctl stop cyclosafe.service***. Respecte le délai configuré (`$SHUTDOWN_DELAY`), vérifie que le service a bien été arrêté (log de warning le cas échéant) et passe le raspberry en mode halt (extinction du bus d'alimentation, du bus USB, et consommation minimale de 23mA environ).

### Variables d'environnement liées

> **SHUTDOWN_DELAY** : ajuste le temps du sleep  entre la commande d'arrêt du service cyclosafed.service et l'extinction du raspberry. La valeur du sleep étant définie à **SHUTDOWN_DELAY + 1**.

> **CYCLOSAFE_LOGS** : définit le répertoire où on_off.log est enregistré

## bq34z100.py

Implémente un driver python minimal de la jauge de batterie **TI BQ34Z100-G1** (I2C, adresse `0x55`) permettant de lire la tension du pack, le courant instantané/moyen, l'état de charge (SOC), la capacité restante et la température. Utilisé par **gpio.py** :
- la tension du pack sert à déclencher l'arrêt du raspberry (seuil `NBR_CELLS * MIN_VOLTAGE`)
- l'état de charge calculé par la jauge est comparé à `LOW_BATTERY_PERCENT` pour signaler une batterie faible

> La tension et le SOC renvoyés ne sont fiables que si la jauge a été configurée (chimie, capacité, nombre de cellules) et calibrée (Voltage Divider, courant) au préalable via les outils TI (bqStudio).

## battery_monitor.py

Utilitaire affichant en continu les mesures de la jauge (tension, courant, puissance, état de charge, capacité, température) à l'aide de **bq34z100.py** : ***python3 ./battery_monitor.py***

## launch_wrapper.sh

Script lancé au démarrage par [**cyclosafed.service**](../setup/systemd/README#cyclosafedservice).

Service ayant plusieurs fonctions :

- sourcer l'environnement ROS puis lancer la [**launch  description principale**](../src/cyclosafe/README.md#launch-description)
  - si l'espace restant sur la carte SD est inférieur à `LOW_STORAGE_TRESHOLD`, les données mesurées ne seront pas enregistrées.
- monitoring de la launch description de la [**launch  description principale**] : si un des noeuds ne se lance pas correctement ou s'arrête en cours d'exécution, l'ensemble des noeuds sont relancés.
- log du démarrage/arrêt des mesures dans ***$CYCLOSAFE_LOGS/cyclosafe.log***

### Variables d'environnement liées

> **LOW_STORAGE_TRESHOLD** : espace de stockage (en MO) disponible en dessous duquel l'enregistrement n'est pas lancé.

> **CYCLOSAFE_LOGS** : définit le répertoire où on_off.log est enregistré