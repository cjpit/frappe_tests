from frappe.integrations.doctype.ldap_settings import ldap_settings
from frappe import new_doc, get_doc, ValidationError, _
from unittest.mock import MagicMock, patch
import pytest
import sys
import ldap3
import ssl


def set_dummy_ldap_settings(settings):
    settings.ldap_server_url = "ldap://whatever.whatever:389"
    settings.organizational_unit = "something"
    settings.base_dn = "whatever"
    settings.password = "hioooo"
    settings.ldap_search_string = "sid={0}"
    settings.ldap_first_name_field = "first_name"
    settings.ldap_email_field = "email"
    settings.ldap_username_field = "username"
    settings.enabled = True


def test_validation_ldap_search_string_needs_to_contain_a_placeholder_for_format(db_transaction):
    with pytest.raises(ValidationError,
                       match="LDAP Search String needs to end with a placeholder, eg sAMAccountName={0}"):
        settings = get_doc("LDAP Settings")
        set_dummy_ldap_settings(settings)
        settings.ldap_search_string = 'notvalid'
        settings.save()


def test_validation_enabling_ldap_must_try_to_connect_to_ldap(db_transaction):
    with patch("frappe.integrations.doctype.ldap_settings.ldap_settings.connect_to_ldap") as mocked_connect_to_ldap:
        settings = get_doc("LDAP Settings")
        set_dummy_ldap_settings(settings)
        settings.enabled = True
        settings.save()
        mocked_connect_to_ldap.assert_called_once()


def test_validation_enabling_ldap_must_test_for_connection_and_not_save_when_errors(db_transaction):
    with patch("frappe.integrations.doctype.ldap_settings.ldap_settings.connect_to_ldap",
               side_effect=OSError('boom')) as mocked_connect_to_ldap:
        settings = get_doc("LDAP Settings")
        set_dummy_ldap_settings(settings)
        settings.enabled = True
        with pytest.raises(OSError):
            settings.save()


@pytest.fixture()
def no_ldap3_module():
    tmpldap = sys.modules['ldap3']
    sys.modules['ldap3'] = None
    yield
    sys.modules['ldap3'] = tmpldap


def test_connect_to_ldap_throws_validation_error_when_ldap3_not_found(db_transaction,
                                                                      no_ldap3_module):
    with pytest.raises(ValidationError, match='Please Install the ldap3 library via pip to use ldap functionality.'):
        ldap_settings.connect_to_ldap("test",
                                      "test",
                                      "test",
                                      "test",
                                      "test",
                                      None,
                                      None,
                                      None)


def test_connect_to_ldap_throws_validation_error_when_invalid_login(db_transaction):
    with patch("ldap3.Connection",
               side_effect=ldap3.core.exceptions.LDAPInvalidCredentialsResult("blah")):
        with pytest.raises(ValidationError, match="Invalid Credentials"):

            ldap_settings.connect_to_ldap("test",
                                          "test",
                                          "test",
                                          "test",
                                          "test",
                                          None,
                                          None,
                                          None)


def test_connect_to_ldap_catches_any_other_error(db_transaction):
    with patch("ldap3.Connection",
               side_effect=IOError("blah")):
        with pytest.raises(ValidationError):

            ldap_settings.connect_to_ldap("test",
                                          "test",
                                          "test",
                                          "test",
                                          "test",
                                          None,
                                          None,
                                          None)


def test_connect_to_ldap_cert_required_if_trusted_cert_set(db_transaction):
    with patch("ldap3.Server", autospec=True, create=True) as mm_server:
        with patch("ldap3.Connection") as mm_connection:
            ldap_settings.connect_to_ldap("test",
                                          "test",
                                          "test",
                                          "test",
                                          trusted_cert="Yes",
                                          ca_certs_file=None,
                                          server_cert_file=None,
                                          private_key_file=None)
            assert(mm_server.call_args[1]["tls"].validate == ssl.CERT_REQUIRED)


def test_connect_to_ldap_cert_ignored_if_trusted_cert_not_set(db_transaction):
    with patch("ldap3.Server", autospec=True, create=True) as mm_server:
        with patch("ldap3.Connection") as mm_connection:
            ldap_settings.connect_to_ldap("test",
                                          "test",
                                          "test",
                                          "test",
                                          trusted_cert="No",
                                          ca_certs_file=None,
                                          server_cert_file=None,
                                          private_key_file=None)

            assert(mm_server.call_args[1]["tls"].validate == ssl.CERT_NONE)


def test_connect_to_ldap_cert_path_to_key_files_correctly_set(db_transaction):
    with patch("ldap3.Server", autospec=True, create=True) as mm_server:
        with patch("ldap3.Connection") as mm_connection:
            ldap_settings.connect_to_ldap("test",
                                          "test",
                                          "test",
                                          "test",
                                          trusted_cert="Yes",
                                          private_key_file="/path/to/priv.pem",
                                          server_cert_file="/path/to/server.pem",
                                          ca_certs_file="/path/to/cacerts.pem")
            assert(mm_server.call_args[1]["tls"].ca_certs_file == "/path/to/cacerts.pem")
            assert (mm_server.call_args[1]["tls"].private_key_file == "/path/to/priv.pem")
            assert (mm_server.call_args[1]["tls"].certificate_file == "/path/to/server.pem")


def test_connect_to_ldap_do_tls_connection_before_binding_if_tls(db_transaction):
    with patch("ldap3.Server", autospec=True, create=True) as mm_server:
        with patch("ldap3.Connection") as mm_connection:
            ldap_settings.connect_to_ldap("test",
                                          "test",
                                          "test",
                                          ssl_tls_mode="StartTLS",
                                          trusted_cert="whatever",
                                          ca_certs_file=None,
                                          server_cert_file=None,
                                          private_key_file=None)

            assert(mm_connection.call_args[1]["auto_bind"] == ldap3.AUTO_BIND_TLS_BEFORE_BIND)


def test_authenticating_ldap_user_only_when_enabled(db_transaction):
    settings = get_doc("LDAP Settings")
    set_dummy_ldap_settings(settings)
    settings.enabled = False
    with patch("frappe.get_doc") as mm_get_doc:
        mm_get_doc.return_value = settings
        with pytest.raises(ValidationError,
                           match="LDAP is not enabled."):
            ldap_settings.authenticate_ldap_user()


def test_authenticating_ldap_user_throws_not_valid_user_when_search_not_found(db_transaction):
    settings = get_doc("LDAP Settings")
    set_dummy_ldap_settings(settings)
    with patch("frappe.get_doc") as mm_get_doc:
        mm_get_doc.return_value = settings
        with patch("frappe.integrations.doctype.ldap_settings.ldap_settings.connect_to_ldap") as mm_conn_ldap:
            mocked_server = MagicMock()
            mm_conn_ldap.return_value = mocked_server
            mocked_server.entries = []
            with pytest.raises(ValidationError,
                               match="Not a valid LDAP user"):
                ldap_settings.authenticate_ldap_user()


def test_authenticating_ldap_user_creates_user_if_not_in_database(db_instance,
                                                                  db_transaction):
    with patch("frappe.integrations.doctype.ldap_settings.ldap_settings.connect_to_ldap") as mm_conn_ldap:

        new_user_email = 'billy@test.com'
        new_user_first_name = 'Billy'
        new_user_username = 'bill'

        settings = get_doc("LDAP Settings")
        settings.ldap_email_field = "email"
        settings.ldap_username_field = "username"
        settings.ldap_first_name_field = "first_name"
        settings.ldap_search_string = "cn={0}"
        settings.organizational_unit = "ou=test,o=lab"
        settings.ldap_server_url = "test"
        settings.base_dn = "test"
        settings.password = "whatever"
        settings.enabled = True
        settings.save()

        server = ldap3.Server('my_fake_server')
        connection = ldap3.Connection(server,
                                      user='cn=bill,ou=test,o=lab',
                                      password='my_password',
                                      client_strategy=ldap3.MOCK_SYNC)
        connection.strategy.add_entry("cn={0},ou=test,o=lab".format(new_user_username),
                                      {"first_name": new_user_first_name,
                                       "email": new_user_email,
                                       "username": new_user_username
                                       })
        connection.bind()

        mm_conn_ldap.return_value = connection
        assert(not db_instance.exists("User", new_user_email))
        ldap_settings.authenticate_ldap_user(new_user_username,
                                             "whatever")
        assert(db_instance.exists("User", new_user_email))
        new_user = get_doc("User",
                           new_user_email)

        assert(new_user.first_name == new_user_first_name)
        assert (new_user.username == new_user_username)
        assert(new_user.email == new_user_email)


def test_authenticating_ldap_user_updates_user_if_in_database(db_instance,
                                                                  db_transaction):
    with patch("frappe.integrations.doctype.ldap_settings.ldap_settings.connect_to_ldap") as mm_conn_ldap:

        new_user_email = 'billy@test.com'
        new_user_first_name = 'Billy'
        new_user_username = 'bill'

        settings = get_doc("LDAP Settings")
        settings.ldap_email_field = "email"
        settings.ldap_username_field = "username"
        settings.ldap_first_name_field = "first_name"
        settings.ldap_search_string = "cn={0}"
        settings.organizational_unit = "ou=test,o=lab"
        settings.ldap_server_url = "test"
        settings.base_dn = "cn=bill,ou=test,o=lab"
        settings.password = "whatever"
        settings.enabled = True
        settings.save()

        user = {
            "doctype": "User",
            "first_name": "JIM",
            "email": new_user_email,
            "username": "JIMMY",
            "send_welcome_email": 0,
            "language": "",
            "user_type": "System User",
            "roles": [{
                "role": _("Blogger")
            }]
        }

        # insert the existing user.
        get_doc(user).insert(ignore_permissions=True)

        server = ldap3.Server('my_fake_server')
        connection = ldap3.Connection(server,
                                      user='cn=bill,ou=test,o=lab',
                                      password='my_password',
                                      client_strategy=ldap3.MOCK_SYNC)
        connection.strategy.add_entry("cn={0},ou=test,o=lab".format(new_user_username),
                                      {"first_name": new_user_first_name,
                                       "email": new_user_email,
                                       "username": new_user_username
                                       })
        connection.bind()

        mm_conn_ldap.return_value = connection
        assert(db_instance.exists("User", new_user_email))
        ldap_settings.authenticate_ldap_user(new_user_username,
                                             "whatever")
        assert(db_instance.exists("User", new_user_email))
        new_user = get_doc("User",
                           new_user_email)

        assert(new_user.first_name == new_user_first_name)
        assert (new_user.username == new_user_username)


def test_get_ldap_client_settings_no_method_set_when_ldap_not_enabled(db_transaction):

    settings = get_doc("LDAP Settings")
    set_dummy_ldap_settings(settings)
    settings.enabled = False
    settings.save()
    result = ldap_settings.get_ldap_client_settings()
    assert(result == {"enabled": False})


def test_get_ldap_client_settings_method_set_when_ldap_is_enabled(db_transaction):
    with patch("frappe.integrations.doctype.ldap_settings.ldap_settings.connect_to_ldap") as mocked_connect_to_ldap:
        settings = get_doc("LDAP Settings")
        set_dummy_ldap_settings(settings)
        settings.enabled = True
        settings.save()
        result = ldap_settings.get_ldap_client_settings()
        assert (result == {"enabled": True,
                           "method": "frappe.integrations.doctype.ldap_settings.ldap_settings.login"})


















