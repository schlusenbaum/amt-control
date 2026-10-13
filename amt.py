#!/usr/bin/env python3
import argparse
import getpass
import os
import json
from pathlib import Path
import ssl
import sys
import uuid
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET


SOAP = "http://www.w3.org/2003/05/soap-envelope"
WSA = "http://schemas.xmlsoap.org/ws/2004/08/addressing"
WSMAN = "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
TRANSFER = "http://schemas.xmlsoap.org/ws/2004/09/transfer"

RESOURCE_COMPUTER_SYSTEM = (
    "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
    "CIM_ComputerSystem"
)


RESOURCE_POWER_MANAGEMENT_SERVICE = (
    "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
    "CIM_PowerManagementService"
)


class AMTClient:
    def __init__(self, host, port, username, protocol, password=None):
        if protocol not in ("http", "https"):
            raise ValueError(
                f"Ungültiges Protokoll {protocol!r}; "
                "erlaubt sind http und https."
            )
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.protocol = protocol
        self.endpoint = f"{protocol}://{host}:{port}/wsman"

        # Vorläufige Kompatibilität mit älterer AMT-TLS-Implementierung.
        # ACHTUNG: Zertifikatsprüfung ist für den Funktionstest deaktiviert.
        # Vor produktivem Einsatz muss die Zertifikatsprüfung aktiviert werden.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
            context.options |= ssl.OP_LEGACY_SERVER_CONNECT
        context.set_ciphers("DEFAULT:@SECLEVEL=0")

        self.context = context

    def request(
        self, resource_uri, selectors, action_uri=None, body_builder=None
    ):
        password = self.password or os.environ.get("AMT_PASSWORD") or getpass.getpass(
            f"AMT-Passwort für {self.username}@{self.host}: "
        )

        manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        manager.add_password(
            None, self.endpoint, self.username, password
        )

        if self.protocol == "https":
            transport_handler = urllib.request.HTTPSHandler(
                context=self.context
            )
        else:
            transport_handler = urllib.request.HTTPHandler()

        opener = urllib.request.build_opener(
            transport_handler,
            urllib.request.HTTPDigestAuthHandler(manager),
        )

        for prefix, namespace in (
            ("s", SOAP),
            ("a", WSA),
            ("w", WSMAN),
        ):
            ET.register_namespace(prefix, namespace)

        envelope = ET.Element(f"{{{SOAP}}}Envelope")
        header = ET.SubElement(envelope, f"{{{SOAP}}}Header")

        to = ET.SubElement(header, f"{{{WSA}}}To")
        to.text = self.endpoint

        action = ET.SubElement(
            header,
            f"{{{WSA}}}Action",
            {f"{{{SOAP}}}mustUnderstand": "true"},
        )
        action.text = action_uri or f"{TRANSFER}/Get"

        message_id = ET.SubElement(
            header, f"{{{WSA}}}MessageID"
        )
        message_id.text = "uuid:" + str(uuid.uuid4())

        reply_to = ET.SubElement(
            header, f"{{{WSA}}}ReplyTo"
        )
        address = ET.SubElement(
            reply_to, f"{{{WSA}}}Address"
        )
        address.text = (
            "http://schemas.xmlsoap.org/ws/2004/08/addressing/"
            "role/anonymous"
        )

        uri = ET.SubElement(
            header,
            f"{{{WSMAN}}}ResourceURI",
            {f"{{{SOAP}}}mustUnderstand": "true"},
        )
        uri.text = resource_uri

        max_size = ET.SubElement(
            header,
            f"{{{WSMAN}}}MaxEnvelopeSize",
            {f"{{{SOAP}}}mustUnderstand": "true"},
        )
        max_size.text = "153600"

        timeout = ET.SubElement(
            header, f"{{{WSMAN}}}OperationTimeout"
        )
        timeout.text = "PT30S"

        selector_set = ET.SubElement(
            header, f"{{{WSMAN}}}SelectorSet"
        )

        for name, value in selectors.items():
            selector = ET.SubElement(
                selector_set,
                f"{{{WSMAN}}}Selector",
                {"Name": name},
            )
            selector.text = value

        body = ET.SubElement(envelope, f"{{{SOAP}}}Body")
        if body_builder is not None:
            body_builder(body)

        payload = ET.tostring(
            envelope,
            encoding="utf-8",
            xml_declaration=True,
        )

        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={
                "Content-Type": "application/soap+xml;charset=UTF-8"
            },
            method="POST",
        )

        try:
            with opener.open(request, timeout=40) as response:
                response_data = response.read()

        except urllib.error.HTTPError as error:
            details = error.read().decode(
                "utf-8", errors="replace"
            ).strip()

            if error.code == 401:
                message = (
                    "AMT-Anmeldung fehlgeschlagen (HTTP 401). "
                    "Benutzername und Kennwort prüfen."
                )
            elif error.code == 403:
                message = (
                    "AMT hat den Zugriff verweigert (HTTP 403). "
                    "Berechtigungen prüfen."
                )
            else:
                message = f"AMT antwortet mit HTTP {error.code}."

            if details:
                message += f" Antwort: {details[:1500]}"

            raise RuntimeError(message) from error

        except urllib.error.URLError as error:
            reason = getattr(error, "reason", error)
            raise RuntimeError(
                "AMT-Kommunikation fehlgeschlagen. "
                f"Verbindung oder Timeout prüfen: {reason}"
            ) from error

        except TimeoutError as error:
            raise RuntimeError(
                "Zeitüberschreitung bei der AMT-Anfrage. "
                "Ob ein Power-Befehl bereits ausgeführt wurde, "
                "ist möglicherweise unklar."
            ) from error

        except Exception as error:
            raise RuntimeError(
                f"AMT-Anfrage fehlgeschlagen "
                f"({type(error).__name__}): {error}"
            ) from error

        try:
            root = ET.fromstring(response_data)
        except ET.ParseError as error:
            raise RuntimeError(
                "AMT hat keine gültige SOAP-XML-Antwort geliefert. "
                "Der Ausgang eines Power-Befehls kann unklar sein."
            ) from error

        fault = next(
            (
                element
                for element in root.iter()
                if element.tag.rsplit("}", 1)[-1] == "Fault"
            ),
            None,
        )

        if fault is not None:
            fault_details = " ".join(
                text.strip()
                for text in fault.itertext()
                if text and text.strip()
            )
            raise RuntimeError(
                f"AMT hat einen SOAP Fault zurückgegeben: "
                f"{fault_details or 'Keine Fehlerdetails vorhanden.'}"
            )

        return root

    def status(self):
        root = self.request(
            RESOURCE_COMPUTER_SYSTEM,
            {
                "CreationClassName": "CIM_ComputerSystem",
                "Name": "ManagedSystem",
            },
        )

        result = {}
        wanted = {
            "EnabledState",
            "HealthState",
            "OperationalStatus",
            "RequestedState",
        }

        for element in root.iter():
            name = element.tag.rsplit("}", 1)[-1]
            if name in wanted:
                result[name] = element.text

        return result

    def _request_power_state(self, state_code):
        """Fordert das Einschalten des verwalteten Rechners an."""

        def build_body(body):
            method_input = ET.SubElement(
                body,
                f"{{{RESOURCE_POWER_MANAGEMENT_SERVICE}}}"
                "RequestPowerStateChange_INPUT",
            )

            power_state = ET.SubElement(
                method_input,
                f"{{{RESOURCE_POWER_MANAGEMENT_SERVICE}}}PowerState",
            )
            power_state.text = str(state_code)

            managed_element = ET.SubElement(
                method_input,
                f"{{{RESOURCE_POWER_MANAGEMENT_SERVICE}}}ManagedElement",
            )

            address = ET.SubElement(
                managed_element,
                f"{{{WSA}}}Address",
            )
            address.text = f"{WSA}/role/anonymous"

            reference_parameters = ET.SubElement(
                managed_element,
                f"{{{WSA}}}ReferenceParameters",
            )

            resource_uri = ET.SubElement(
                reference_parameters,
                f"{{{WSMAN}}}ResourceURI",
            )
            resource_uri.text = RESOURCE_COMPUTER_SYSTEM

            selector_set = ET.SubElement(
                reference_parameters,
                f"{{{WSMAN}}}SelectorSet",
            )

            for name, value in (
                ("Name", "ManagedSystem"),
                ("CreationClassName", "CIM_ComputerSystem"),
            ):
                selector = ET.SubElement(
                    selector_set,
                    f"{{{WSMAN}}}Selector",
                    {"Name": name},
                )
                selector.text = value

        root = self.request(
            RESOURCE_POWER_MANAGEMENT_SERVICE,
            {
                "Name": "Intel(r) AMT Power Management Service",
                "SystemName": "Intel(r) AMT",
                "CreationClassName": "CIM_PowerManagementService",
                "SystemCreationClassName": "CIM_ComputerSystem",
            },
            action_uri=(
                f"{RESOURCE_POWER_MANAGEMENT_SERVICE}/"
                "RequestPowerStateChange"
            ),
            body_builder=build_body,
        )

        return_value = None
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] == "ReturnValue":
                return_value = element.text
                break

        if return_value is None:
            raise RuntimeError(
                "AMT-Antwort enthält keinen ReturnValue."
            )

        if return_value != "0":
            raise RuntimeError(
                f"AMT hat den Power-State {state_code} abgelehnt. "
                f"ReturnValue: {return_value}"
            )

        return return_value


    def start(self):
        """Fordert das Einschalten des Rechners an."""
        return self._request_power_state(2)

    def stop(self):
        """Fordert das Ausschalten des Rechners an."""
        return self._request_power_state(8)

    def reset(self):
        """Fordert einen Hardware-Reset des Rechners an."""
        return self._request_power_state(10)


def load_hosts():
    """Lädt die Rechnerkonfiguration aus hosts.json."""
    config_path = Path(__file__).resolve().with_name("hosts.json")

    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            hosts = json.load(config_file)
    except FileNotFoundError as error:
        raise RuntimeError(
            f"Konfigurationsdatei fehlt: {config_path}"
        ) from error
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Ungültige JSON-Konfiguration in {config_path}: {error}"
        ) from error

    if not isinstance(hosts, dict):
        raise RuntimeError("hosts.json muss ein JSON-Objekt enthalten.")

    for name, config in hosts.items():
        if not isinstance(config, dict):
            raise RuntimeError(
                f"Ungültige Konfiguration für Rechner {name!r}."
            )

        for key in ("host", "port", "protocol", "username"):
            if key not in config:
                raise RuntimeError(
                    f"Bei Rechner {name!r} fehlt der Eintrag {key!r}."
                )

        if config["protocol"] not in ("http", "https"):
            raise RuntimeError(
                f"Ungültiges Protokoll für Rechner {name!r}: "
                f"{config["protocol"]!r}. Erlaubt sind http und https."
            )

    return hosts


HOSTS = load_hosts()




def main():
    parser = argparse.ArgumentParser(
        description="Intel-AMT-Verwaltung über Python und WS-Man"
    )
    parser.add_argument(
        "-u", "--user", dest="username",
        help="AMT-Benutzername; überschreibt hosts.json"
    )
    parser.add_argument(
        "-p", "--password", dest="password",
        help="AMT-Kennwort"
    )
    parser.add_argument(
        "command", choices=("list", "status", "start", "stop", "reset"),
        help="auszuführender Befehl"
    )
    parser.add_argument(
        "host", nargs="?",
        help="Name des konfigurierten AMT-Rechners"
    )
    args = parser.parse_args()

    if args.command == "list":
        for name, config in HOSTS.items():
            print(f"{name}: {config['host']}:{config['port']}")
        return 0

    if not args.host:
        parser.error(
            f"Für {args.command} muss ein Rechnername angegeben werden"
        )

    if args.host not in HOSTS:
        print(f"Unbekannter Rechner: {args.host}", file=sys.stderr)
        print("Verfügbar:", ", ".join(HOSTS), file=sys.stderr)
        return 2

    config = HOSTS[args.host]
    client = AMTClient(
        config["host"],
        config["port"],
        args.username or config["username"],
        config["protocol"],
        args.password,
    )

    if args.command in ("start", "stop", "reset"):
        try:
            if args.command == "start":
                client.start()
                action = "Einschaltbefehl"
            elif args.command == "stop":
                client.stop()
                action = "Ausschaltbefehl"
            else:
                client.reset()
                action = "Neustartbefehl"
        except RuntimeError as error:
            print(error, file=sys.stderr)
            return 1

        print(
            f"{action} von AMT für "
            f"{args.host} ({config['host']}) bestätigt."
        )
        return 0

    try:
        result = client.status()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1

    print(f"Rechner: {args.host} ({config['host']})")
    labels = {
        "EnabledState": "Betriebszustand",
        "HealthState": "Gesundheitszustand",
        "OperationalStatus": "Betriebsstatus",
        "RequestedState": "Angeforderter Zustand",
    }

    if not result:
        print("Keine bekannten Statusfelder in der Antwort gefunden.")
        return 1

    for key, label in labels.items():
        if key in result:
            print(f"{label}: {result[key]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
