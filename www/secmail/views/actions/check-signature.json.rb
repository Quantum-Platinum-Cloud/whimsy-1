#
# check signature on an attachment
#

month, hash = @message.match(%r{/(\d+)/(\w+)}).captures

mbox = Mailbox.new(month)
message = mbox.find(hash)

begin
  # fetch attachment and signature
  attachment = message.find(@attachment).as_file
  signature  = message.find(@signature).as_file

  # run gpg verify command
  out, err, rc = Open3.capture3 'gpg', '--verify', signature.path,
    attachment.path

  # if key is not found, fetch and try again
  if err.include? "gpg: Can't check signature: public key not found"
    # extract and fetch key
    keyid = err[/[RD]SA key ID (\w+)/,1].untaint
    out2, err2, rc2 = Open3.capture3 'gpg', '--keyserver', 'pgpkeys.mit.edu',
      '--recv-keys', keyid

    # run gpg verify command again
    out, err, rc = Open3.capture3 'gpg', '--verify', signature.path,
      attachment.path

    # if verify failed, concatenate fetch output
    if rc.exitstatus != 0
      out += out2
      err += err2
    end
  end

  # list of strings to ignore
  ignore = [
    /^gpg:\s+WARNING: This key is not certified with a trusted signature!$/,
    /^gpg:\s+There is no indication that the signature belongs to the owner\.$/
  ]

  ignore.each {|re| err.gsub! re, ''}

ensure
  attachment.unlink if attachment
  signature.unlink if signature
end

{output: out, error: err, rc: rc.exitstatus}
