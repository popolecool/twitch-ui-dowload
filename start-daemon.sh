#!/bin/bash
# Script de démarrage du daemon Twitch Recorder

# Couleurs pour l'affichage
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}Twitch Stream Recorder Daemon${NC}"
echo -e "${GREEN}==================================${NC}"

# Détecter le répertoire du script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${YELLOW}Répertoire de travail: ${SCRIPT_DIR}${NC}"

# Vérifier si Python 3 est installé
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Erreur: Python 3 n'est pas installé${NC}"
    exit 1
fi

# Vérifier si streamlink est installé
if ! command -v streamlink &> /dev/null; then
    echo -e "${RED}Erreur: Streamlink n'est pas installé${NC}"
    echo -e "${YELLOW}Installez-le avec: pip3 install streamlink${NC}"
    exit 1
fi

# Vérifier si les fichiers de configuration existent
if [ ! -f "config.json" ]; then
    echo -e "${YELLOW}Avertissement: config.json non trouvé, configuration par défaut sera utilisée${NC}"
fi

if [ ! -f "streams.json" ]; then
    echo -e "${YELLOW}Avertissement: streams.json non trouvé, liste de streams vide${NC}"
fi

# Créer les dossiers nécessaires
mkdir -p recordings temp_segments

echo -e "${GREEN}Vérifications terminées avec succès${NC}"
echo -e "${GREEN}Démarrage du daemon...${NC}"
echo ""

# Activer l'environnement virtuel si présent
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activation de l'environnement virtuel...${NC}"
    source venv/bin/activate
fi

# Démarrer le daemon
python3 daemon.py

# Code de sortie
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo -e "${RED}Le daemon s'est arrêté avec le code d'erreur: ${EXIT_CODE}${NC}"
else
    echo -e "${GREEN}Le daemon s'est arrêté proprement${NC}"
fi

exit $EXIT_CODE
