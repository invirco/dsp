<?xml version='1.0'?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:template match ="/">
    <HTML xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <SCRIPT language="JScript">
    <xsl:comment>
      <![CDATA[
      function showSuppressed() {
        document.getElementById("ShowSuppressedButton").style.display = "none";

        var i, msg = document.getElementsByTagName("PRE");

        for (i = 0; i < msg.length; i++)
          msg[i].style.display = "block";
      }
      ]]>
    </xsl:comment>
    </SCRIPT>						

    <BODY>
      <xsl:apply-templates select="DOCUMENT"/>
    </BODY>
    </HTML>
  </xsl:template>

  <xsl:template match="DOCUMENT">
    <H1> Linker messages </H1>
    <I> Generated on <xsl:value-of select="@gen_time"/></I>
    <BR/><BR/>
    <xsl:if test="MSG[@suppressed]">
      <INPUT name="ShowSuppressed" type="button" value="Show suppressed messages" onclick="showSuppressed();" id="ShowSuppressedButton"/>
    </xsl:if>
    <HR size="2" noshade="1"/>
    <xsl:apply-templates select="MSG"/>
  </xsl:template>

  <xsl:template match="MSG[@type='Error']">
    <PRE>
      <xsl:if test="@suppressed"><xsl:attribute name="style">display:none</xsl:attribute></xsl:if>
      <font color="#FF0000">[Error <xsl:value-of select="@mid"/>]</font>
      <xsl:apply-templates select="FILE"/><xsl:apply-templates select="FILE_LINE"/>&#x20;<xsl:value-of select="TEXT"/>
    </PRE>
    <xsl:apply-templates select="EXTENDED_INFO"/>
  </xsl:template> 

  <xsl:template match="MSG[@type='Warning']">
    <PRE>
      <xsl:if test="@suppressed"><xsl:attribute name="style">display:none</xsl:attribute></xsl:if>
      <font color="#0000FF">[Warning <xsl:value-of select="@mid"/>]</font>
      <xsl:apply-templates select="FILE"/><xsl:apply-templates select="FILE_LINE"/>&#x20;<xsl:value-of select="TEXT"/>
    </PRE>
    <xsl:apply-templates select="EXTENDED_INFO"/>
  </xsl:template> 

  <xsl:template match="MSG[@type='Informational']">
    <PRE>
      <xsl:if test="@suppressed"><xsl:attribute name="style">display:none</xsl:attribute></xsl:if>
      <font color="#008000">[Info <xsl:value-of select="@mid"/>]</font>
      <xsl:apply-templates select="FILE"/><xsl:apply-templates select="FILE_LINE"/>&#x20;<xsl:value-of select="TEXT"/>
    </PRE>
    <xsl:apply-templates select="EXTENDED_INFO"/>
  </xsl:template> 

  <xsl:template match="EXTENDED_INFO">
    <PRE><SMALL><xsl:value-of select="current()"/></SMALL></PRE>
  </xsl:template>

  <xsl:template match="FILE">
    <I>&#x20;<xsl:value-of select="current()"/></I>
  </xsl:template>                        

  <xsl:template match="FILE_LINE">
    <I>:<xsl:value-of select="current()"/></I>
  </xsl:template>

</xsl:stylesheet>