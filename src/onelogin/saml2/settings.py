# -*- coding: utf-8 -*-

""" OneLogin_Saml2_Settings class

Copyright (c) 2014, OneLogin, Inc.
All rights reserved.

Setting class of OneLogin's Python Toolkit.

"""
from datetime import datetime
import re
from os.path import dirname, exists, join, sep

from onelogin.saml2 import compat
from onelogin.saml2.constants import OneLogin_Saml2_Constants
from onelogin.saml2.errors import OneLogin_Saml2_Error
from onelogin.saml2.metadata import OneLogin_Saml2_Metadata
from onelogin.saml2.utils import OneLogin_Saml2_Utils
from onelogin.saml2.xml_utils import OneLogin_Saml2_XML

try:
    import ujson as json
except ImportError:
    import json

# Regex from Django Software Foundation and individual contributors.
# Released under a BSD 3-Clause License
url_regex = re.compile(
    r'^(?:[a-z0-9\.\-]*)://'  # scheme is validated separately
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
    r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)
url_schemes = ['http', 'https', 'ftp', 'ftps']


def validate_url(url):
    """
    Auxiliary method to validate an urllib
    :param url: An url to be validated
    :type url: string
    :returns: True if the url is valid
    :rtype: bool
    """

    scheme = url.split('://')[0].lower()
    if scheme not in url_schemes:
        return False
    if not bool(url_regex.search(url)):
        return False
    return True


class OneLogin_Saml2_Settings(object):
    """

    Handles the settings of the Python toolkits.

    """

    def __init__(self, settings=None, custom_base_path=None, sp_validation_only=False):
        """
        Initializes the settings:
        - Sets the paths of the different folders
        - Loads settings info from settings file or array/object provided

        :param settings: SAML Toolkit Settings
        :type settings: dict|object

        :param custom_base_path: Path where are stored the settings file and the cert folder
        :type custom_base_path: string

        :param sp_validation_only: Avoid the IdP validation
        :type sp_validation_only: boolean
        """
        self.__sp_validation_only = sp_validation_only
        self.__paths = {}
        self.__strict = False
        self.__debug = False
        self.__sp = {}
        self.__idp = {}
        self.__security = {}
        self.__contacts = {}
        self.__organization = {}
        self.__errors = []

        self.__load_paths(base_path=custom_base_path)
        self.__update_paths(settings)

        if settings is None:
            try:
                valid = self.__load_settings_from_file()
            except Exception as e:
                raise e
            if not valid:
                raise OneLogin_Saml2_Error(
                    'Invalid dict settings at the file: %s',
                    OneLogin_Saml2_Error.SETTINGS_INVALID,
                    ','.join(self.__errors)
                )
        elif isinstance(settings, dict):
            if not self.__load_settings_from_dict(settings):
                raise OneLogin_Saml2_Error(
                    'Invalid dict settings: %s',
                    OneLogin_Saml2_Error.SETTINGS_INVALID,
                    ','.join(self.__errors)
                )
        else:
            raise Exception('Unsupported settings object')

        self.format_idp_cert()
        self.format_sp_cert()
        self.format_sp_key()

    def __load_paths(self, base_path=None):
        """
        Sets the paths of the different folders
        """
        if base_path is None:
            base_path = dirname(dirname(dirname(__file__)))
        if not base_path.endswith(sep):
            base_path += sep
        self.__paths = {
            'base': base_path,
            'cert': base_path + 'certs' + sep,
            'lib': base_path + 'lib' + sep,
            'extlib': base_path + 'extlib' + sep,
        }

    def __update_paths(self, settings):
        """
        Set custom paths if necessary
        """
        if not isinstance(settings, dict):
            return

        if 'custom_base_path' in settings:
            base_path = settings['custom_base_path']
            base_path = join(dirname(__file__), base_path)
            self.__load_paths(base_path)

    def get_base_path(self):
        """
        Returns base path

        :return: The base toolkit folder path
        :rtype: string
        """
        return self.__paths['base']

    def get_cert_path(self):
        """
        Returns cert path

        :return: The cert folder path
        :rtype: string
        """
        return self.__paths['cert']

    def get_lib_path(self):
        """
        Returns lib path

        :return: The library folder path
        :rtype: string
        """
        return self.__paths['lib']

    def get_ext_lib_path(self):
        """
        Returns external lib path

        :return: The external library folder path
        :rtype: string
        """
        return self.__paths['extlib']

    def get_schemas_path(self):
        """
        Returns schema path

        :return: The schema folder path
        :rtype: string
        """
        return self.__paths['lib'] + 'schemas/'

    def __load_settings_from_dict(self, settings):
        """
        Loads settings info from a settings Dict

        :param settings: SAML Toolkit Settings
        :type settings: dict

        :returns: True if the settings info is valid
        :rtype: boolean
        """
        errors = self.check_settings(settings)
        if len(errors) == 0:
            self.__errors = []
            self.__sp = settings['sp']
            self.__idp = settings['idp']

            if 'strict' in settings:
                self.__strict = settings['strict']
            if 'debug' in settings:
                self.__debug = settings['debug']
            if 'security' in settings:
                self.__security = settings['security']
            else:
                self.__security = {}
            if 'contactPerson' in settings:
                self.__contacts = settings['contactPerson']
            if 'organization' in settings:
                self.__organization = settings['organization']

            self.__add_default_values()
            return True

        self.__errors = errors
        return False

    def __load_settings_from_file(self):
        """
        Loads settings info from the settings json file

        :returns: True if the settings info is valid
        :rtype: boolean
        """
        filename = self.get_base_path() + 'settings.json'

        if not exists(filename):
            raise OneLogin_Saml2_Error(
                'Settings file not found: %s',
                OneLogin_Saml2_Error.SETTINGS_FILE_NOT_FOUND,
                filename
            )

        # In the php toolkit instead of being a json file it is a php file and
        # it is directly included
        with open(filename, 'r') as json_data:
            settings = json.loads(json_data.read())

        advanced_filename = self.get_base_path() + 'advanced_settings.json'
        if exists(advanced_filename):
            with open(advanced_filename, 'r') as json_data:
                settings.update(json.loads(json_data.read()))  # Merge settings

        return self.__load_settings_from_dict(settings)

    def __add_default_values(self):
        """
        Add default values if the settings info is not complete
        """
        if 'assertionConsumerService' not in self.__sp:
            self.__sp['assertionConsumerService'] = {}
        if 'binding' not in self.__sp['assertionConsumerService']:
            self.__sp['assertionConsumerService']['binding'] = OneLogin_Saml2_Constants.BINDING_HTTP_POST

        if 'singleLogoutService' not in self.__sp:
            self.__sp['singleLogoutService'] = {}
        if 'binding' not in self.__sp['singleLogoutService']:
            self.__sp['singleLogoutService']['binding'] = OneLogin_Saml2_Constants.BINDING_HTTP_REDIRECT

        if 'singleLogoutService' not in self.__idp:
            self.__idp['singleLogoutService'] = {}

        # Related to nameID
        if 'NameIDFormat' not in self.__sp:
            self.__sp['NameIDFormat'] = OneLogin_Saml2_Constants.NAMEID_UNSPECIFIED
        if 'nameIdEncrypted' not in self.__security:
            self.__security['nameIdEncrypted'] = False

        # Sign provided
        if 'authnRequestsSigned' not in self.__security:
            self.__security['authnRequestsSigned'] = False
        if 'logoutRequestSigned' not in self.__security:
            self.__security['logoutRequestSigned'] = False
        if 'logoutResponseSigned' not in self.__security:
            self.__security['logoutResponseSigned'] = False
        if 'signMetadata' not in self.__security:
            self.__security['signMetadata'] = False

        # Metadata format
        if 'metadataValidUntil' not in self.__security.keys():
            self.__security['metadataValidUntil'] = None  # None means use default
        if 'metadataCacheDuration' not in self.__security.keys():
            self.__security['metadataCacheDuration'] = None  # None means use default

        # Sign expected
        if 'wantMessagesSigned' not in self.__security:
            self.__security['wantMessagesSigned'] = False
        if 'wantAssertionsSigned' not in self.__security:
            self.__security['wantAssertionsSigned'] = False

        # Encrypt expected
        if 'wantAssertionsEncrypted' not in self.__security:
            self.__security['wantAssertionsEncrypted'] = False
        if 'wantNameIdEncrypted' not in self.__security:
            self.__security['wantNameIdEncrypted'] = False

        # Signature Algorithm
        if 'signatureAlgorithm' not in self.__security.keys():
            self.__security['signatureAlgorithm'] = OneLogin_Saml2_Constants.RSA_SHA1

        if 'x509cert' not in self.__idp:
            self.__idp['x509cert'] = ''
        if 'certFingerprint' not in self.__idp:
            self.__idp['certFingerprint'] = ''
        if 'certFingerprintAlgorithm' not in self.__idp:
            self.__idp['certFingerprintAlgorithm'] = 'sha1'

        if 'x509cert' not in self.__sp:
            self.__sp['x509cert'] = ''
        if 'privateKey' not in self.__sp:
            self.__sp['privateKey'] = ''

        if 'requestedAuthnContext' not in self.__security:
            self.__security['requestedAuthnContext'] = True

    def check_settings(self, settings):
        """
        Checks the settings info.

        :param settings: Dict with settings data
        :type settings: dict

        :returns: Errors found on the settings data
        :rtype: list
        """
        assert isinstance(settings, dict)

        errors = []
        if not isinstance(settings, dict) or len(settings) == 0:
            errors.append('invalid_syntax')
        else:
            if not self.__sp_validation_only:
                errors += self.check_idp_settings(settings)
            sp_errors = self.check_sp_settings(settings)
            errors += sp_errors

        return errors

    def check_idp_settings(self, settings):
        """
        Checks the IdP settings info.
        :param settings: Dict with settings data
        :type settings: dict
        :returns: Errors found on the IdP settings data
        :rtype: list
        """
        assert isinstance(settings, dict)

        errors = []
        if not isinstance(settings, dict) or len(settings) == 0:
            errors.append('invalid_syntax')
        else:
            if 'idp' not in settings or len(settings['idp']) == 0:
                errors.append('idp_not_found')
            else:
                idp = settings['idp']
                if 'entityId' not in idp or len(idp['entityId']) == 0:
                    errors.append('idp_entityId_not_found')

                if 'singleSignOnService' not in idp or \
                    'url' not in idp['singleSignOnService'] or \
                        len(idp['singleSignOnService']['url']) == 0:
                    errors.append('idp_sso_not_found')
                elif not validate_url(idp['singleSignOnService']['url']):
                    errors.append('idp_sso_url_invalid')

                if 'singleLogoutService' in idp and \
                    'url' in idp['singleLogoutService'] and \
                    len(idp['singleLogoutService']['url']) > 0 and \
                        not validate_url(idp['singleLogoutService']['url']):
                    errors.append('idp_slo_url_invalid')

                if 'security' in settings:
                    security = settings['security']

                    exists_x509 = ('x509cert' in idp and
                                   len(idp['x509cert']) > 0)
                    exists_fingerprint = ('certFingerprint' in idp and
                                          len(idp['certFingerprint']) > 0)

                    want_assert_sign = 'wantAssertionsSigned' in security.keys() and security['wantAssertionsSigned']
                    want_mes_signed = 'wantMessagesSigned' in security.keys() and security['wantMessagesSigned']
                    nameid_enc = 'nameIdEncrypted' in security.keys() and security['nameIdEncrypted']

                    if (want_assert_sign or want_mes_signed) and \
                            not(exists_x509 or exists_fingerprint):
                        errors.append('idp_cert_or_fingerprint_not_found_and_required')
                    if nameid_enc and not exists_x509:
                        errors.append('idp_cert_not_found_and_required')
        return errors

    def check_sp_settings(self, settings):
        """
        Checks the SP settings info.
        :param settings: Dict with settings data
        :type settings: dict
        :returns: Errors found on the SP settings data
        :rtype: list
        """
        assert isinstance(settings, dict)

        errors = []
        if not isinstance(settings, dict) or len(settings) == 0:
            errors.append('invalid_syntax')
        else:
            if 'sp' not in settings or len(settings['sp']) == 0:
                errors.append('sp_not_found')
            else:
                # check_sp_certs uses self.__sp so I add it
                old_sp = self.__sp
                self.__sp = settings['sp']

                sp = settings['sp']
                security = {}
                if 'security' in settings:
                    security = settings['security']

                if 'entityId' not in sp or len(sp['entityId']) == 0:
                    errors.append('sp_entityId_not_found')

                if 'assertionConsumerService' not in sp or \
                    'url' not in sp['assertionConsumerService'] or \
                        len(sp['assertionConsumerService']['url']) == 0:
                    errors.append('sp_acs_not_found')
                elif not validate_url(sp['assertionConsumerService']['url']):
                    errors.append('sp_acs_url_invalid')

                if 'singleLogoutService' in sp and \
                    'url' in sp['singleLogoutService'] and \
                    len(sp['singleLogoutService']['url']) > 0 and \
                        not validate_url(sp['singleLogoutService']['url']):
                    errors.append('sp_sls_url_invalid')

                if 'signMetadata' in security and isinstance(security['signMetadata'], dict):
                    if 'keyFileName' not in security['signMetadata'] or \
                            'certFileName' not in security['signMetadata']:
                        errors.append('sp_signMetadata_invalid')

                authn_sign = 'authnRequestsSigned' in security and security['authnRequestsSigned']
                logout_req_sign = 'logoutRequestSigned' in security and security['logoutRequestSigned']
                logout_res_sign = 'logoutResponseSigned' in security and security['logoutResponseSigned']
                want_assert_enc = 'wantAssertionsEncrypted' in security and security['wantAssertionsEncrypted']
                want_nameid_enc = 'wantNameIdEncrypted' in security and security['wantNameIdEncrypted']

                if not self.check_sp_certs():
                    if authn_sign or logout_req_sign or logout_res_sign or \
                       want_assert_enc or want_nameid_enc:
                        errors.append('sp_cert_not_found_and_required')

            if 'contactPerson' in settings:
                types = settings['contactPerson']
                valid_types = ['technical', 'support', 'administrative', 'billing', 'other']
                for c_type in types:
                    if c_type not in valid_types:
                        errors.append('contact_type_invalid')
                        break

                for c_type in settings['contactPerson']:
                    contact = settings['contactPerson'][c_type]
                    if ('givenName' not in contact or len(contact['givenName']) == 0) or \
                            ('emailAddress' not in contact or len(contact['emailAddress']) == 0):
                        errors.append('contact_not_enought_data')
                        break

            if 'organization' in settings:
                for org in settings['organization']:
                    organization = settings['organization'][org]
                    if ('name' not in organization or len(organization['name']) == 0) or \
                        ('displayname' not in organization or len(organization['displayname']) == 0) or \
                            ('url' not in organization or len(organization['url']) == 0):
                        errors.append('organization_not_enought_data')
                        break
        # Restores the value that had the self.__sp
        if 'old_sp' in locals():
            self.__sp = old_sp

        return errors

    def check_sp_certs(self):
        """
        Checks if the x509 certs of the SP exists and are valid.

        :returns: If the x509 certs of the SP exists and are valid
        :rtype: boolean
        """
        key = self.get_sp_key()
        cert = self.get_sp_cert()
        return key is not None and cert is not None

    def get_sp_key(self):
        """
        Returns the x509 private key of the SP.

        :returns: SP private key
        :rtype: string
        """
        key = self.__sp.get('privateKey')
        if not key:
            key_file_name = self.__paths['cert'] + 'sp.key'

            if exists(key_file_name):
                with open(key_file_name, 'r') as f_key:
                    key = self.__sp['privateKey'] = f_key.read()
        return key or None

    def get_sp_cert(self):
        """
        Returns the x509 public cert of the SP.

        :returns: SP public cert
        :rtype: string
        """
        cert = self.__sp.get('x509cert')
        if not cert:
            cert_file_name = self.__paths['cert'] + 'sp.crt'
            if exists(cert_file_name):
                with open(cert_file_name, 'r') as f_cert:
                    cert = self.__sp['x509cert'] = f_cert.read()
        return cert or None

    def get_idp_cert(self):
        """
        Returns the x509 public cert of the IdP.

        :returns: IdP public cert
        :rtype: string
        """
        return self.__idp['x509cert'] or None

    def get_idp_data(self):
        """
        Gets the IdP data.

        :returns: IdP info
        :rtype: dict
        """
        return self.__idp

    def get_sp_data(self):
        """
        Gets the SP data.

        :returns: SP info
        :rtype: dict
        """
        return self.__sp

    def get_security_data(self):
        """
        Gets security data.

        :returns: Security info
        :rtype: dict
        """
        return self.__security

    def get_contacts(self):
        """
        Gets contact data.

        :returns: Contacts info
        :rtype: dict
        """
        return self.__contacts

    def get_organization(self):
        """
        Gets organization data.

        :returns: Organization info
        :rtype: dict
        """
        return self.__organization

    def get_sp_metadata(self):
        """
        Gets the SP metadata. The XML representation.
        :returns: SP metadata (xml)
        :rtype: string
        """
        metadata = OneLogin_Saml2_Metadata.builder(
            self.__sp, self.__security['authnRequestsSigned'],
            self.__security['wantAssertionsSigned'],
            self.__security['metadataValidUntil'],
            self.__security['metadataCacheDuration'],
            self.get_contacts(), self.get_organization()
        )
        cert = self.get_sp_cert()
        metadata = OneLogin_Saml2_Metadata.add_x509_key_descriptors(metadata, cert)

        # Sign metadata
        if 'signMetadata' in self.__security and self.__security['signMetadata'] is not False:
            if self.__security['signMetadata'] is True:
                # Use the SP's normal key to sign the metadata:
                if not cert:
                    raise OneLogin_Saml2_Error(
                        'Cannot sign metadata: missing SP public key certificate.',
                        OneLogin_Saml2_Error.PUBLIC_CERT_FILE_NOT_FOUND
                    )
                cert_metadata = cert
                key_metadata = self.get_sp_key()
                if not key_metadata:
                    raise OneLogin_Saml2_Error(
                        'Cannot sign metadata: missing SP private key.',
                        OneLogin_Saml2_Error.PRIVATE_KEY_FILE_NOT_FOUND
                    )
            else:
                # Use a custom key to sign the metadata:
                if ('keyFileName' not in self.__security['signMetadata'] or
                        'certFileName' not in self.__security['signMetadata']):
                    raise OneLogin_Saml2_Error(
                        'Invalid Setting: signMetadata value of the sp is not valid',
                        OneLogin_Saml2_Error.SETTINGS_INVALID_SYNTAX
                    )
                key_file_name = self.__security['signMetadata']['keyFileName']
                cert_file_name = self.__security['signMetadata']['certFileName']
                key_metadata_file = self.__paths['cert'] + key_file_name
                cert_metadata_file = self.__paths['cert'] + cert_file_name

                try:
                    with open(key_metadata_file, 'r') as f_metadata_key:
                        key_metadata = f_metadata_key.read()
                except IOError:
                    raise OneLogin_Saml2_Error(
                        'Private key file not readable: %s',
                        OneLogin_Saml2_Error.PRIVATE_KEY_FILE_NOT_FOUND,
                        key_metadata_file
                    )

                try:
                    with open(cert_metadata_file, 'r') as f_metadata_cert:
                        cert_metadata = f_metadata_cert.read()
                except IOError:
                    raise OneLogin_Saml2_Error(
                        'Public cert file not readable: %s',
                        OneLogin_Saml2_Error.PUBLIC_CERT_FILE_NOT_FOUND,
                        cert_metadata_file
                    )

            metadata = OneLogin_Saml2_Metadata.sign_metadata(metadata, key_metadata, cert_metadata)

        return metadata

    def validate_metadata(self, xml):
        """
        Validates an XML SP Metadata.

        :param xml: Metadata's XML that will be validate
        :type xml: string

        :returns: The list of found errors
        :rtype: list
        """

        assert isinstance(xml, compat.text_types)

        if len(xml) == 0:
            raise Exception('Empty string supplied as input')

        errors = []
        root = OneLogin_Saml2_XML.validate_xml(xml, 'saml-schema-metadata-2.0.xsd', self.__debug)
        if isinstance(root, str):
            errors.append(root)
        else:
            if root.tag != '{%s}EntityDescriptor' % OneLogin_Saml2_Constants.NS_MD:
                errors.append('noEntityDescriptor_xml')
            else:
                if (len(root.findall('.//md:SPSSODescriptor', namespaces=OneLogin_Saml2_Constants.NSMAP))) != 1:
                    errors.append('onlySPSSODescriptor_allowed_xml')
                else:
                    valid_until, cache_duration = root.get('validUntil'), root.get('cacheDuration')

                    if valid_until:
                        valid_until = OneLogin_Saml2_Utils.parse_SAML_to_time(valid_until)
                    expire_time = OneLogin_Saml2_Utils.get_expire_time(cache_duration, valid_until)
                    if expire_time is not None and int(datetime.now().strftime('%s')) > int(expire_time):
                        errors.append('expired_xml')

        # TODO: Validate Sign

        return errors

    def format_idp_cert(self):
        """
        Formats the IdP cert.
        """
        self.__idp['x509cert'] = OneLogin_Saml2_Utils.format_cert(self.__idp['x509cert'])

    def format_sp_cert(self):
        """
        Formats the SP cert.
        """
        self.__sp['x509cert'] = OneLogin_Saml2_Utils.format_cert(self.__sp['x509cert'])

    def format_sp_key(self):
        """
        Formats the private key.
        """
        self.__sp['privateKey'] = OneLogin_Saml2_Utils.format_private_key(self.__sp['privateKey'])

    def get_errors(self):
        """
        Returns an array with the errors, the array is empty when the settings is ok.

        :returns: Errors
        :rtype: list
        """
        return self.__errors

    def set_strict(self, value):
        """
        Activates or deactivates the strict mode.

        :param value: Strict parameter
        :type value: boolean
        """
        assert isinstance(value, bool)

        self.__strict = value

    def is_strict(self):
        """
        Returns if the 'strict' mode is active.

        :returns: Strict parameter
        :rtype: boolean
        """
        return self.__strict

    def is_debug_active(self):
        """
        Returns if the debug is active.

        :returns: Debug parameter
        :rtype: boolean
        """
        return self.__debug
