import ldap from 'ldapjs';

const username = 'tranquochuy';
const password = '123456';

const client = ldap.createClient({
    url: 'ldap://localhost:389'
});

client.bind('cn=admin,dc=example,dc=com', 'admin', (err) => {
    if (err) {
        console.error('❌ Admin bind failed:', err.message);
        return;
    }

    const baseDN = 'dc=example,dc=com';
    const searchOptions = {
        scope: 'sub',
        filter: `(uid=${username})`
    };

    client.search(baseDN, searchOptions, (err, res) => {
        if (err) {
            console.error('❌ Search error:', err.message);
            client.unbind();
            return;
        }

        let userDN = null;

        res.on('searchEntry', (entry) => {
            userDN = entry.objectName.toString();
        });

        res.on('end', () => {
            if (!userDN) {
                console.error('❌ User not found with uid=' + username);
                client.unbind();
                return;
            }

            console.log('✅ Found DN:', userDN);

            // Bind với user để xác thực
            const authClient = ldap.createClient({ url: 'ldap://localhost:389' });

            authClient.bind(userDN, password, (err) => {
                if (err) {
                    console.error('❌ Invalid credentials:', err.message);
                } else {
                    console.log('✅ LDAP login success!');
                }
                authClient.unbind();
            });

            client.unbind();
        });
    });
});
